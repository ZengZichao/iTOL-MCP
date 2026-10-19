"""组 F：系统工具（工具 31–33，见《04 §4.7》）。"""

from __future__ import annotations

import importlib.metadata
import os
import stat
import sys
from pathlib import Path

import httpx

from itol_mcp.config import write_api_key
from itol_mcp.services.template_service import list_template_types
from itol_mcp.tools.common import MCPServerLike, Runtime, execute
from itol_mcp.utils.constants import (
    EXPORT_FORMATS,
    HEALTH_CHECK_TIMEOUT,
    ITOL_BASE,
    KEY_ENV_VAR,
)
from itol_mcp.utils.result import ToolResult


def register(server: MCPServerLike, runtime: Runtime) -> None:
    """向 MCP 服务器注册系统工具。"""

    @server.tool(
        name="itol_server_info",
        description=(
            "返回服务器版本、运行环境、配置状态（密钥是否已配置——仅布尔值，不回显内容）、"
            "工作区路径、可用导出格式与模板类型数量。用于客户端初始化探测。"
        ),
    )
    def itol_server_info() -> dict:
        """查询服务器信息。"""
        return execute(runtime.logger, "itol_server_info", lambda: _server_info_impl(runtime))

    @server.tool(
        name="itol_health_check",
        description=(
            "自检依赖导入、工作区可写性、iTOL 端点可达性（HEAD，超时 5s）、密钥文件权限提示与模板注册表完整性。"
            "返回逐项 checks [{name, status, detail}] 与 healthy 总判定。"
        ),
    )
    def itol_health_check() -> dict:
        """执行服务器健康检查。"""
        return execute(runtime.logger, "itol_health_check", lambda: _health_check_impl(runtime))

    @server.tool(
        name="itol_config_set_api_key",
        description=(
            "将 iTOL API Key 写入本机密钥文件（权限 600，内容不回显），用于首次配置或轮换。"
            "key_file 缺省为 ~/.config/itol-mcp/.itolapi.key。"
            "注意：密钥仅在本调用内存在，请勿在对话中复述。"
        ),
    )
    def itol_config_set_api_key(api_key: str = "", key_file: str | None = None) -> dict:
        """写入 API Key 到本机密钥文件。"""
        return execute(
            runtime.logger,
            "itol_config_set_api_key",
            lambda: _set_api_key_impl(runtime, api_key, key_file),
        )


# ---------------------------------------------------------------------------
# 实现
# ---------------------------------------------------------------------------


def _server_info_impl(runtime: Runtime) -> ToolResult:
    from itol_mcp._version import __version__

    data = {
        "version": __version__,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "sdk_version": _sdk_version(),
        "transport": runtime.transport,
        "workspace_dir": str(runtime.workspace.root),
        "api_key_configured": _api_key_configured(runtime),
        "export_formats": list(EXPORT_FORMATS),
        "template_types_count": len(list_template_types()),
    }
    return ToolResult.ok(
        f"iTOL-MCP v{data['version']}（SDK {data['sdk_version']}，Python {data['python_version']}）",
        data,
    )


def _sdk_version() -> str:
    try:
        return importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


def _api_key_configured(runtime: Runtime) -> bool:
    if os.environ.get(KEY_ENV_VAR):
        return True
    key_file = runtime.config.effective_key_file()
    return key_file.is_file() and key_file.stat().st_size > 0


def _health_check_impl(runtime: Runtime) -> ToolResult:
    checks: list[dict] = []

    # 1) 依赖
    deps = ["mcp", "dendropy", "pandas", "httpx", "yaml", "pydantic"]
    problems = [d for d in deps if not _importable(d)]
    checks.append(
        {
            "name": "dependencies",
            "status": "OK" if not problems else "ERROR",
            "detail": "全部依赖导入正常" if not problems else f"导入失败：{problems}",
        }
    )

    # 2) 工作区可写
    probe = runtime.workspace.root / ".health_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(
            {
                "name": "workspace_writable",
                "status": "OK",
                "detail": f"工作区可写：{runtime.workspace.root}",
            }
        )
    except OSError as exc:
        checks.append(
            {"name": "workspace_writable", "status": "ERROR", "detail": f"工作区不可写：{exc}"}
        )

    # 3) iTOL 端点可达
    try:
        resp = httpx.head(f"{ITOL_BASE}/help.cgi", timeout=HEALTH_CHECK_TIMEOUT)
        reached = resp.status_code < 500
        checks.append(
            {
                "name": "itol_reachable",
                "status": "OK" if reached else "WARN",
                "detail": f"iTOL 端点可达（HTTP {resp.status_code}）"
                if reached
                else f"iTOL 端点返回异常状态 HTTP {resp.status_code}",
            }
        )
    except httpx.HTTPError as exc:
        checks.append(
            {
                "name": "itol_reachable",
                "status": "WARN",
                "detail": f"iTOL 端点不可达（{exc}），网络受限时导出/上传不可用",
            }
        )

    # 4) 密钥文件
    key_file = runtime.config.effective_key_file()
    if not _api_key_configured(runtime):
        checks.append(
            {
                "name": "api_key",
                "status": "WARN",
                "detail": "未配置 API Key：上传/删除不可用，导出可用（可通过 api_key 参数、环境变量 ITOL_API_KEY 或 itol_config_set_api_key 配置）",
            }
        )
    else:
        mode = stat.S_IMODE(key_file.stat().st_mode)
        if mode & 0o077:
            checks.append(
                {
                    "name": "api_key",
                    "status": "WARN",
                    "detail": f"密钥文件权限过宽（{oct(mode)}），建议 chmod 600 {key_file}",
                }
            )
        else:
            checks.append(
                {"name": "api_key", "status": "OK", "detail": f"API Key 已配置（{key_file}）"}
            )

    # 5) 模板注册表
    n_types = len(list_template_types())
    checks.append(
        {
            "name": "template_registry",
            "status": "OK" if n_types >= 32 else "WARN",
            "detail": f"模板注册表完整（{n_types} 种）"
            if n_types >= 32
            else f"模板类型数异常（{n_types} < 32）",
        }
    )

    healthy = all(c["status"] == "OK" for c in checks)
    return ToolResult.ok(
        "健康检查完成：" + ("全部正常" if healthy else "存在需关注项（WARN/ERROR）"),
        {"checks": checks, "healthy": healthy},
    )


def _importable(module_name: str) -> bool:
    import importlib

    try:
        importlib.import_module(module_name)
        return True
    except ImportError:  # pragma: no cover
        return False


def _set_api_key_impl(runtime: Runtime, api_key: str, key_file: str | None) -> ToolResult:
    if not (api_key or "").strip():
        from itol_mcp.exceptions import UsageError

        raise UsageError("参数 api_key 必填（明文密钥仅在本调用内存在，内容不回显）")
    target = (
        Path(key_file).expanduser().resolve() if key_file else runtime.config.effective_key_file()
    )
    written = write_api_key(api_key, target)
    data = {
        "key_file": str(written),
        "written": True,
        "hint": "请勿分享或提交该密钥文件；如怀疑泄露请立即轮换 iTOL API Key",
    }
    return ToolResult.ok(
        f"API Key 已写入 {written}（权限 600，内容不回显）",
        data,
    )
