"""配置与密钥管理（实现设计第 5.2 节）。

- ``ServerConfig``：服务器运行时配置（工作区/密钥文件/超时/重试/日志）；
- ``load_config``：命令行覆写 > 配置文件 ``itol_mcp.yaml`` > 环境变量 > 默认值；
- ``resolve_api_key``：工具参数 > 环境变量 ``ITOL_API_KEY`` > 密钥文件（权限 600）；
- ``write_api_key``：写入密钥文件（mkdir + chmod 600 + 内容校验）。
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from itol_mcp.exceptions import APIKeyError, ConfigError
from itol_mcp.utils.constants import (
    DEFAULT_KEY_FILE,
    DEFAULT_WORKSPACE_NAME,
    KEY_ENV_VAR,
    KEY_FILE_ENV_VAR,
    LOG_LEVEL_ENV_VAR,
    WORKSPACE_ENV_VAR,
)

_DEFAULT_CONFIG_NAME = "itol_mcp.yaml"


@dataclass
class ServerConfig:
    """服务器配置。"""

    workspace_dir: Path | None = None
    key_file: str = DEFAULT_KEY_FILE
    export_dir: Path | None = None
    template_dir: Path | None = None
    timeout: float = 120.0
    max_retries: int = 3
    backoff_factor: float = 1.0
    max_file_bytes: int = 50 * 1024 * 1024
    max_upload_files: int = 50
    max_rows: int = 200_000
    log_level: str = "INFO"
    strict_permissions: bool = False
    extra: dict = field(default_factory=dict)

    def effective_workspace(self, cwd: Path | None = None) -> Path:
        """解析最终工作区路径（环境变量优先，其次显式配置，最后 cwd 下默认目录）。"""
        env_ws = os.environ.get(WORKSPACE_ENV_VAR)
        if env_ws:
            ws = Path(env_ws).expanduser().resolve()
        elif self.workspace_dir is not None:
            ws = Path(self.workspace_dir).expanduser().resolve()
        else:
            base = cwd or Path.cwd()
            ws = (base / DEFAULT_WORKSPACE_NAME).resolve()
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def effective_key_file(self) -> Path:
        env_kf = os.environ.get(KEY_FILE_ENV_VAR)
        if env_kf:
            return Path(env_kf).expanduser().resolve()
        return Path(self.key_file).expanduser().resolve()

    def effective_export_dir(self, workspace: Path) -> Path:
        if self.export_dir is not None:
            p = Path(self.export_dir).expanduser().resolve()
        else:
            p = workspace / "exports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def effective_template_dir(self, workspace: Path) -> Path:
        if self.template_dir is not None:
            p = Path(self.template_dir).expanduser().resolve()
        else:
            p = workspace / "templates"
        p.mkdir(parents=True, exist_ok=True)
        return p


def load_config(
    overrides: dict | None = None, config_path: str | Path | None = None
) -> ServerConfig:
    """加载配置。

    优先级（低 → 高）：代码默认值 < 配置文件 < ``overrides``（命令行覆写）。
    """
    overrides = overrides or {}
    cfg = ServerConfig()

    path = config_path
    if path is None:
        candidate = Path.cwd() / _DEFAULT_CONFIG_NAME
        path = candidate if candidate.is_file() else None
    if path is not None:
        cfg = _apply_yaml(cfg, Path(path))

    level = os.environ.get(LOG_LEVEL_ENV_VAR)
    if level:
        cfg.log_level = level

    for key, value in overrides.items():
        if value is None or not hasattr(cfg, key):
            continue
        setattr(cfg, key, value)
    return cfg


def _apply_yaml(cfg: ServerConfig, path: Path) -> ServerConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"配置文件解析失败：{path}（{exc}）") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"配置文件格式错误：{path}（应为键值映射）")
    allowed = {
        "workspace_dir",
        "key_file",
        "export_dir",
        "template_dir",
        "timeout",
        "max_retries",
        "backoff_factor",
        "max_file_bytes",
        "max_upload_files",
        "max_rows",
        "log_level",
        "strict_permissions",
    }
    for key, value in raw.items():
        if key in allowed:
            setattr(cfg, key, value)
        else:
            cfg.extra[key] = value
    return cfg


def validate_api_key_format(key: str) -> str:
    """校验密钥格式：单行、8–128 字符、无换行/控制字符。"""
    stripped = key.strip()
    if not stripped:
        raise APIKeyError("API Key 不能为空")
    if any(c in stripped for c in ("\n", "\r", "\t")):
        raise APIKeyError("API Key 含换行或制表符，请确认粘贴内容")
    if any(ord(c) < 32 for c in stripped):
        raise APIKeyError("API Key 含控制字符，请确认粘贴内容")
    if not (8 <= len(stripped) <= 128):
        raise APIKeyError("API Key 长度需在 8–128 字符之间")
    return stripped


def resolve_api_key(
    explicit: str | None = None,
    env_name: str = KEY_ENV_VAR,
    key_file: Path | None = None,
    strict_permissions: bool = False,
) -> tuple[str, str]:
    """解析 API Key，返回 ``(key, source)``。

    优先级：显式参数 > 环境变量 > 密钥文件；均无则抛 ``APIKeyError``。
    """
    if explicit and explicit.strip():
        return validate_api_key_format(explicit), "参数"

    env_key = os.environ.get(env_name)
    if env_key and env_key.strip():
        return validate_api_key_format(env_key), "环境变量 ITOL_API_KEY"

    if key_file is None:
        key_file = Path(DEFAULT_KEY_FILE).expanduser().resolve()
    else:
        key_file = Path(key_file).expanduser().resolve()
    if key_file.is_file():
        return _read_key_file(key_file, strict_permissions), f"密钥文件 {key_file}"

    raise APIKeyError(
        "未找到 iTOL API Key。请通过工具参数 api_key、环境变量 ITOL_API_KEY "
        "或运行 `itol-mcp --set-api-key` 写入密钥文件后再试。上传/删除功能必需密钥，导出可选。"
    )


def _read_key_file(key_file: Path, strict: bool = False) -> str:
    """读取密钥文件并校验权限位。"""
    try:
        mode = stat.S_IMODE(key_file.stat().st_mode)
    except OSError as exc:
        raise APIKeyError(f"无法读取密钥文件：{key_file}（{exc}）") from exc
    if strict and (mode & 0o077):
        raise APIKeyError(
            f"密钥文件权限过宽（{oct(mode)}），已按 strict_permissions 设置拒绝读取；"
            f"请执行 chmod 600 {key_file}"
        )
    try:
        content = key_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise APIKeyError(f"无法读取密钥文件：{key_file}（{exc}）") from exc
    if not content:
        raise APIKeyError(f"密钥文件为空：{key_file}")
    return validate_api_key_format(content)


def write_api_key(key: str, key_file: Path) -> Path:
    """写入 API Key 到密钥文件：mkdir + 校验 + chmod 600。

    返回写入后的文件路径（内容不回显）。
    """
    validated = validate_api_key_format(key)
    key_file = Path(key_file).expanduser().resolve()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        key_file.write_text(validated + "\n", encoding="utf-8")
        os.chmod(key_file, 0o600)
    except OSError as exc:
        raise APIKeyError(f"写入密钥文件失败：{key_file}（{exc}）") from exc
    return key_file


def key_file_permission_hint(key_file: Path) -> str | None:
    """返回密钥文件权限提示（权限过宽时），无问题返回 None。"""
    key_file = Path(key_file).expanduser().resolve()
    if not key_file.is_file():
        return None
    mode = stat.S_IMODE(key_file.stat().st_mode)
    if mode & 0o077:
        return f"密钥文件权限过宽（{oct(mode)}），建议 chmod 600 {key_file}"
    return None
