"""配置与密钥管理测试：配置加载优先级、密钥校验/解析/写入、权限提示。"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

import pytest

from itol_mcp.config import (
    ServerConfig,
    key_file_permission_hint,
    load_config,
    resolve_api_key,
    validate_api_key_format,
    write_api_key,
)
from itol_mcp.exceptions import APIKeyError, ConfigError

# ---------------------------------------------------------------------------
# ServerConfig 路径解析
# ---------------------------------------------------------------------------


def test_effective_workspace_precedence_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ITOL_MCP_WORKSPACE", str(tmp_path / "env_ws"))
    cfg = ServerConfig(workspace_dir=tmp_path / "cfg_ws")
    assert cfg.effective_workspace(cwd=tmp_path) == (tmp_path / "env_ws").resolve()


def test_effective_workspace_fallback_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ITOL_MCP_WORKSPACE", raising=False)
    cfg = ServerConfig(workspace_dir=tmp_path / "cfg_ws")
    got = cfg.effective_workspace(cwd=tmp_path)
    assert got == (tmp_path / "cfg_ws").resolve()
    assert got.is_dir()


def test_effective_workspace_default_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ITOL_MCP_WORKSPACE", raising=False)
    cfg = ServerConfig()
    got = cfg.effective_workspace(cwd=tmp_path)
    assert got == (tmp_path / ".itol_mcp_workspace").resolve()


def test_effective_key_file_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ITOL_MCP_KEY_FILE", str(tmp_path / "k" / "key.txt"))
    assert ServerConfig().effective_key_file() == (tmp_path / "k" / "key.txt").resolve()


def test_effective_export_and_template_dirs(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    cfg = ServerConfig(export_dir=tmp_path / "exp", template_dir=tmp_path / "tpl")
    assert cfg.effective_export_dir(ws) == (tmp_path / "exp").resolve()
    assert cfg.effective_template_dir(ws) == (tmp_path / "tpl").resolve()
    # 缺省回落到工作区
    cfg2 = ServerConfig()
    assert cfg2.effective_export_dir(ws) == (ws / "exports").resolve()
    assert cfg2.effective_template_dir(ws) == (ws / "templates").resolve()


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_merges_yaml(tmp_path: Path) -> None:
    cfg_path = tmp_path / "itol_mcp.yaml"
    cfg_path.write_text("timeout: 60\nmax_retries: 5\nunknown_key: 1\n", encoding="utf-8")
    cfg = load_config(config_path=cfg_path)
    assert cfg.timeout == 60
    assert cfg.max_retries == 5
    assert cfg.extra == {"unknown_key": 1}


def test_load_config_overrides_beat_yaml(tmp_path: Path) -> None:
    cfg_path = tmp_path / "itol_mcp.yaml"
    cfg_path.write_text("timeout: 60\n", encoding="utf-8")
    cfg = load_config(overrides={"timeout": 30}, config_path=cfg_path)
    assert cfg.timeout == 30


def test_load_config_bad_yaml(tmp_path: Path) -> None:
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text(": : :\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="解析失败"):
        load_config(config_path=cfg_path)


def test_load_config_non_mapping(tmp_path: Path) -> None:
    cfg_path = tmp_path / "list.yaml"
    cfg_path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="格式错误"):
        load_config(config_path=cfg_path)


# ---------------------------------------------------------------------------
# API Key 校验
# ---------------------------------------------------------------------------


def test_validate_api_key_ok() -> None:
    assert validate_api_key_format("  0123456789abcdef  ") == "0123456789abcdef"


@pytest.mark.parametrize(
    "key, match",
    [
        ("", "不能为空"),
        ("  ", "不能为空"),
        ("short", "长度"),
        ("x" * 129, "长度"),
        ("abc\ndefgh", "换行"),
        ("ab\tcd", "制表符"),
    ],
)
def test_validate_api_key_rejects(key: str, match: str) -> None:
    with pytest.raises(APIKeyError, match=match):
        validate_api_key_format(key)


# ---------------------------------------------------------------------------
# resolve_api_key
# ---------------------------------------------------------------------------


def test_resolve_explicit_precedence() -> None:
    key, source = resolve_api_key(explicit="explicitkey123", env_name="ITOL_API_KEY")
    assert key == "explicitkey123"
    assert source == "参数"


def test_resolve_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ITOL_API_KEY", "envkey12345")
    key, source = resolve_api_key(key_file=tmp_path / "none")
    assert key == "envkey12345"
    assert "环境变量" in source


def test_resolve_key_file(tmp_path: Path) -> None:
    kf = tmp_path / "key.txt"
    write_api_key("filekey12345", kf)
    key, source = resolve_api_key(key_file=kf)
    assert key == "filekey12345"
    assert str(kf) in source


def test_resolve_none_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ITOL_API_KEY", raising=False)
    with pytest.raises(APIKeyError, match="未找到 iTOL API Key"):
        resolve_api_key(key_file=tmp_path / "missing")


def test_resolve_strict_permissions(tmp_path: Path) -> None:
    kf = tmp_path / "key.txt"
    kf.write_text("loosekey12345\n", encoding="utf-8")
    os.chmod(kf, 0o644)
    # 宽松模式可读
    assert resolve_api_key(key_file=kf)[0] == "loosekey12345"
    # strict 模式拒绝
    with pytest.raises(APIKeyError, match="权限过宽"):
        resolve_api_key(key_file=kf, strict_permissions=True)


# ---------------------------------------------------------------------------
# write_api_key
# ---------------------------------------------------------------------------


def test_write_api_key_sets_600(tmp_path: Path) -> None:
    kf = tmp_path / "nested" / "key.txt"
    written = write_api_key("0123456789abcdef", kf)
    assert written == kf.resolve()
    assert kf.read_text(encoding="utf-8").strip() == "0123456789abcdef"
    mode = stat.S_IMODE(kf.stat().st_mode)
    assert mode & 0o077 == 0


def test_write_api_key_invalid(tmp_path: Path) -> None:
    with pytest.raises(APIKeyError, match="不能为空"):
        write_api_key("  ", tmp_path / "k.txt")


# ---------------------------------------------------------------------------
# 补充边缘路径
# ---------------------------------------------------------------------------


def test_validate_api_key_control_char() -> None:
    with pytest.raises(APIKeyError, match="控制字符"):
        validate_api_key_format("abc\x01def")


def test_load_config_log_level_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ITOL_MCP_LOG_LEVEL", "DEBUG")
    cfg = load_config()
    assert cfg.log_level == "DEBUG"


def test_load_config_unknown_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ITOL_MCP_LOG_LEVEL", raising=False)
    cfg = load_config(overrides={"nonexistent_key": 42})
    # 未知键忽略，不报错
    assert cfg is not None


def test_resolve_key_file_empty(tmp_path: Path) -> None:
    kf = tmp_path / "empty.txt"
    kf.write_text("   \n", encoding="utf-8")
    with pytest.raises(APIKeyError, match="为空"):
        resolve_api_key(key_file=kf)


def test_resolve_key_file_stat_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ITOL_API_KEY", raising=False)
    kf = tmp_path / "key.txt"
    kf.write_text("0123456789abc\n", encoding="utf-8")

    def _boom(*args: Any, **kwargs: Any):
        raise OSError("permission denied")

    monkeypatch.setattr("itol_mcp.config.stat.S_IMODE", _boom)
    with pytest.raises(APIKeyError, match="无法读取"):
        resolve_api_key(key_file=kf)


def test_key_file_permission_hint(tmp_path: Path) -> None:
    kf = tmp_path / "key.txt"
    assert key_file_permission_hint(kf) is None  # 不存在
    kf.write_text("0123456789abc\n", encoding="utf-8")
    os.chmod(kf, 0o644)
    hint = key_file_permission_hint(kf)
    assert hint is not None
    assert "权限过宽" in hint
    os.chmod(kf, 0o600)
    assert key_file_permission_hint(kf) is None


def test_resolve_key_file_default_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """key_file=None → 使用默认路径。"""
    monkeypatch.delenv("ITOL_API_KEY", raising=False)
    with pytest.raises(APIKeyError, match="未找到"):
        resolve_api_key(explicit=None)


def test_read_key_file_oserror_on_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_read_key_file 的 read_text OSError。"""
    monkeypatch.delenv("ITOL_API_KEY", raising=False)
    kf = tmp_path / "key.txt"
    kf.write_text("0123456789abc\n", encoding="utf-8")

    def _boom(*args: Any, **kwargs: Any):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", _boom)
    with pytest.raises(APIKeyError, match="无法读取"):
        resolve_api_key(key_file=kf)


def test_write_api_key_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """write_api_key 的 OSError。"""
    kf = tmp_path / "key.txt"

    def _boom(*args: Any, **kwargs: Any):
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "write_text", _boom)
    with pytest.raises(APIKeyError, match="写入密钥文件失败"):
        write_api_key("0123456789abc", kf)
