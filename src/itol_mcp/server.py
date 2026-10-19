"""MCP 服务器装配入口（实现设计第 5.9 节）。

支持两种传输方式：
- stdio（默认）：供 Claude Desktop / Cursor / CatPaw / Claude Code 等客户端注册；
- streamable-http：``itol-mcp --transport http --host 127.0.0.1 --port 8731``。

命令行：
- ``itol-mcp``：stdio 启动；
- ``itol-mcp --set-api-key``：交互式写入 API Key（不回显）；
- ``python -m itol_mcp``：等价于 ``itol-mcp``；
- ``mcp dev src/itol_mcp/server.py``：SDK 调试模式。
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from typing import Any

try:  # mcp >= 2.0：FastMCP 更名为 MCPServer
    from mcp.server.mcpserver import MCPServer as _MCPServer

    _MCP_V2 = True
except ModuleNotFoundError:  # pragma: no cover —— mcp < 2 兼容
    from mcp.server.fastmcp import FastMCP as _MCPServer  # type: ignore[attr-defined,no-redef]

    _MCP_V2 = False

from itol_mcp._version import __version__
from itol_mcp.config import ServerConfig, load_config, write_api_key
from itol_mcp.services.workspace_service import Workspace
from itol_mcp.tools import ALL_PROMPTS, ALL_RESOURCES, ALL_TOOLS, register_all
from itol_mcp.tools.common import Runtime
from itol_mcp.utils.constants import DEFAULT_KEY_FILE
from itol_mcp.utils.logger import get_logger, setup_logging

_INSTRUCTIONS = (
    "iTOL-MCP：基于 MCP 协议的系统发育树（iTOL）可视化自动化服务。"
    "提供 33 个工具（itol_*）、3 个帮助资源与 2 个引导提示，覆盖："
    "工作区文件管理、树解析与校验、分类学提取与单系群分析、iTOL 注释模板生成（32 种类型）、"
    "以及 iTOL 批量上传/导出/删除。所有工具返回统一结构 "
    "{success, message, data, warnings, files}；失败时 success=false 且 message 为中文可读原因。"
)


def create_server(config: ServerConfig | None = None, transport: str = "stdio") -> Any:
    """创建并装配完整的 MCP 服务器（工具/资源/提示全部注册）。"""
    cfg = config or load_config()
    workspace = Workspace(cfg.effective_workspace(cwd=Path.cwd()))
    runtime = Runtime(config=cfg, workspace=workspace, transport=transport)
    setup_logging(workspace.root / "logs", level=cfg.log_level)
    runtime.logger = get_logger()

    kwargs: dict[str, Any] = {"name": "itol-mcp", "instructions": _INSTRUCTIONS}
    if _MCP_V2:
        kwargs["title"] = "iTOL-MCP"
        kwargs["description"] = "iTOL 系统发育树可视化自动化 MCP 服务器"
        kwargs["version"] = __version__
    server = _MCPServer(**kwargs)

    register_all(server, runtime)  # type: ignore[arg-type]
    runtime.logger.info(
        "服务器装配完成：%d 工具 / %d 资源 / %d 提示（transport=%s，工作区=%s）",
        len(ALL_TOOLS),
        len(ALL_RESOURCES),
        len(ALL_PROMPTS),
        transport,
        workspace.root,
    )
    return server


def build_server(config: ServerConfig | None = None) -> Any:
    """公开构建接口（供编程方式嵌入，如 ``from itol_mcp import build_server``）。"""
    return create_server(config)


def _tool_names(server: Any) -> list[str]:
    fn = getattr(server, "list_tools", None)
    if fn is None:
        return []  # pragma: no cover
    return sorted({str(getattr(t, "name", "")) for t in _await(fn)})


def _resource_names(server: Any) -> list[str]:
    fn = getattr(server, "list_resources", None)
    if fn is None:
        return []  # pragma: no cover
    return sorted({str(getattr(r, "uri", "")) for r in _await(fn)})


def _prompt_names(server: Any) -> list[str]:
    fn = getattr(server, "list_prompts", None)
    if fn is None:
        return []  # pragma: no cover
    return sorted({str(getattr(p, "name", "")) for p in _await(fn)})


def _await(fn: Any) -> Any:
    """兼容协程/同步两种枚举接口（mcp v1 同步、v2 协程）。

    - 未运行事件循环时：直接 ``asyncio.run``；
    - 已在事件循环中（如被 MCP 客户端框架调用）：另起线程持独立事件循环执行，
      避免 ``asyncio.run`` 抛出 ``RuntimeError`` 阻塞调用方。
    """
    import asyncio
    import inspect
    import threading

    if not inspect.iscoroutinefunction(fn):
        return fn()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(fn())

    result: list[Any] = []
    error: list[BaseException] = []

    def _worker() -> None:
        try:
            result.append(asyncio.run(fn()))
        except BaseException as exc:  # 跨线程回传任意异常
            error.append(exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


def get_arg_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="itol-mcp",
        description="iTOL-MCP：iTOL 系统发育树可视化自动化 MCP 服务器（v" + __version__ + "）",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="传输方式：stdio（默认）或 http（streamable-http）",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP 模式监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=8731, help="HTTP 模式监听端口（默认 8731）")
    parser.add_argument(
        "--config", default=None, help="配置文件路径（默认读取当前目录 itol_mcp.yaml）"
    )
    parser.add_argument(
        "--workspace", default=None, help="工作区目录（覆盖环境变量 ITOL_MCP_WORKSPACE 与配置）"
    )
    parser.add_argument(
        "--set-api-key", action="store_true", help="交互式写入 iTOL API Key（不回显）后退出"
    )
    parser.add_argument(
        "--key-file",
        default=None,
        help="设置密钥时使用的密钥文件路径（默认 ~/.config/itol-mcp/.itolapi.key）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口；返回进程退出码。"""
    args = get_arg_parser().parse_args(argv)

    if args.set_api_key:
        return _set_api_key_cli(args.key_file)

    overrides: dict[str, object] = {}
    if args.workspace:
        overrides["workspace_dir"] = Path(args.workspace).expanduser().resolve()
    config = load_config(overrides=overrides, config_path=args.config)

    server = create_server(config, transport=args.transport)
    if args.transport == "http":
        print(
            f"iTOL-MCP v{__version__} 已启动：streamable-http @ http://{args.host}:{args.port}/mcp"
        )
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run(transport="stdio")
    return 0


def _set_api_key_cli(key_file: str | None) -> int:
    """交互式密钥写入（getpass 不回显）。"""
    key = getpass.getpass("请输入 iTOL API Key（不回显）: ").strip()
    if not key:
        print("错误：API Key 不能为空", file=sys.stderr)
        return 1
    target = (
        Path(key_file).expanduser().resolve()
        if key_file
        else Path(DEFAULT_KEY_FILE).expanduser().resolve()
    )
    write_api_key(key, target)
    print(f"API Key 已写入 {target}（权限 600，内容不回显；请勿分享或提交该文件）")
    return 0


def run() -> None:
    """console_scripts 入口（``itol-mcp``）。"""
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    run()
