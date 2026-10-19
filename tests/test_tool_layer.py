"""工具层测试：直接调用各模块 *_impl 函数验证参数校验与返回包装。

覆盖：工作区工具、树分析工具、分类学工具、模板工具、系统工具。
"""

from __future__ import annotations

from typing import Any

import pytest

from itol_mcp.exceptions import UsageError, WorkspaceError
from itol_mcp.tools import ALL_PROMPTS, ALL_RESOURCES, ALL_TOOLS
from itol_mcp.tools.common import (
    Runtime,
    execute,
    parse_json,
    pick_one,
    preview_lines,
    provided_pairs,
    split_commas,
    table_to_rows,
)
from itol_mcp.tools.system_tools import (
    _api_key_configured,
    _health_check_impl,
    _server_info_impl,
    _set_api_key_impl,
)
from itol_mcp.tools.workspace_tools import _file_read_impl, _file_write_impl, _workspace_list_impl
from itol_mcp.utils.constants import ITOL_BASE, KEY_ENV_VAR
from itol_mcp.utils.result import ToolResult

# ---------------------------------------------------------------------------
# 工具注册清单
# ---------------------------------------------------------------------------


def test_all_tools_count() -> None:
    assert len(ALL_TOOLS) == 33
    assert len(set(ALL_TOOLS)) == 33


def test_all_resources_count() -> None:
    assert len(ALL_RESOURCES) == 3
    assert all(u.startswith("itol://help/") for u in ALL_RESOURCES)


def test_all_prompts_count() -> None:
    assert len(ALL_PROMPTS) == 2


def test_all_tools_are_prefixed() -> None:
    assert all(t.startswith("itol_") for t in ALL_TOOLS)


# ---------------------------------------------------------------------------
# common 辅助
# ---------------------------------------------------------------------------


def test_provided_pairs_filters_empty() -> None:
    assert provided_pairs({"a": None, "b": "", "c": [], "d": {}, "e": "x"}) == {"e": "x"}


def test_pick_one_single() -> None:
    assert pick_one("组", {"a": None, "b": "x"}) == ("b", "x")


def test_pick_one_none() -> None:
    with pytest.raises(UsageError, match="至少需要"):
        pick_one("组", {"a": None, "b": ""})


def test_pick_one_multiple() -> None:
    with pytest.raises(UsageError, match="互斥"):
        pick_one("组", {"a": "1", "b": "2"})


def test_split_commas() -> None:
    assert split_commas(" a , b ,, c ") == ["a", "b", "c"]
    assert split_commas(None) == []
    assert split_commas("") == []


def test_execute_maps_usage_error(runtime: Runtime) -> None:
    def boom() -> ToolResult:
        raise UsageError("参数非法")

    result = execute(runtime.logger, "t", boom)
    assert result["success"] is False
    assert "参数非法" in result["message"]


def test_execute_maps_internal_error(runtime: Runtime) -> None:
    def boom() -> ToolResult:
        raise ValueError("oops")

    result = execute(runtime.logger, "t", boom)
    assert result["success"] is False
    assert "内部错误" in result["message"]


def test_execute_ok_result(runtime: Runtime) -> None:
    def good() -> ToolResult:
        return ToolResult.ok("ok", {"x": 1})

    result = execute(runtime.logger, "t", good)
    assert result["success"] is True
    assert result["data"] == {"x": 1}


# ---------------------------------------------------------------------------
# 工作区工具
# ---------------------------------------------------------------------------


def test_workspace_list_impl(runtime: Runtime) -> None:
    runtime.workspace.write_text("data/a.nwk", "((A,B),C);")
    res = _workspace_list_impl(runtime, "data")
    assert res.success is True
    assert res.data["count"] == 1
    assert res.data["files"][0]["name"] == "a.nwk"
    assert res.data["files"][0]["kind"] == "tree"


def test_file_write_then_read_impl(runtime: Runtime) -> None:
    w = _file_write_impl(runtime, "data/t.csv", "id,v\nA,1\n", False)
    assert w.success is True
    r = _file_read_impl(runtime, "data/t.csv", 10)
    assert r.success is True
    assert r.data["total_lines"] == 2
    assert "id" in r.data["content"]


def test_file_write_escapes_workspace(runtime: Runtime) -> None:
    with pytest.raises(WorkspaceError, match="越界"):
        runtime.workspace.write_text("../evil.txt", "x")


def test_file_write_forbidden_key(runtime: Runtime) -> None:
    with pytest.raises(WorkspaceError, match="禁止写入"):
        runtime.workspace.write_text(".itolapi.key", "secret")


# ---------------------------------------------------------------------------
# 系统工具
# ---------------------------------------------------------------------------


def test_server_info_impl(runtime: Runtime) -> None:
    res = _server_info_impl(runtime)
    assert res.success is True
    assert res.data["version"] == "0.1.0"
    assert res.data["workspace_dir"] == str(runtime.workspace.root)
    assert res.data["api_key_configured"] is False
    assert len(res.data["export_formats"]) == 8
    assert res.data["template_types_count"] >= 32


def test_set_api_key_impl(runtime: Runtime, tmp_path) -> None:
    from pathlib import Path

    target = Path(tmp_path) / "keys" / "k.txt"
    res = _set_api_key_impl(runtime, "0123456789abcdef", str(target))
    assert res.success is True
    assert target.read_text(encoding="utf-8").strip() == "0123456789abcdef"


def test_set_api_key_empty_rejected(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="api_key 必填"):
        _set_api_key_impl(runtime, "", None)


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------


def test_health_check_impl_healthy(respx_mock, runtime: Runtime) -> None:
    respx_mock.head(f"{ITOL_BASE}/help.cgi").mock(return_value=__import__("respx").MockResponse(200, text="<html>"))
    res = _health_check_impl(runtime)
    checks = {c["name"]: c["status"] for c in res.data["checks"]}
    assert checks["dependencies"] == "OK"
    assert checks["workspace_writable"] == "OK"
    assert checks["template_registry"] == "OK"
    assert "api_key" in checks  # WARN（未配置）
    assert "itol_reachable" in checks


def test_health_check_impl_endpoint_down(respx_mock, runtime: Runtime) -> None:
    respx_mock.head(f"{ITOL_BASE}/help.cgi").mock(return_value=__import__("respx").MockResponse(503, text="boom"))
    res = _health_check_impl(runtime)
    checks = {c["name"]: c["status"] for c in res.data["checks"]}
    assert checks["itol_reachable"] in ("OK", "WARN")


def test_health_check_impl_reachable_ok(respx_mock, runtime: Runtime) -> None:
    respx_mock.head(f"{ITOL_BASE}/help.cgi").mock(return_value=__import__("respx").MockResponse(200, text="<html>"))
    res = _health_check_impl(runtime)
    checks = {c["name"]: c["status"] for c in res.data["checks"]}
    assert checks["itol_reachable"] == "OK"


def test_health_check_http_error(respx_mock, runtime: Runtime, monkeypatch) -> None:
    """iTOL HEAD 请求抛 httpx.HTTPError → itol_reachable=WARN。"""

    def _boom(*args: Any, **kwargs: Any):
        raise __import__("httpx").ConnectError("network down", request=None)

    monkeypatch.setattr("itol_mcp.tools.system_tools.httpx.head", _boom)
    res = _health_check_impl(runtime)
    checks = {c["name"]: c for c in res.data["checks"]}
    assert checks["itol_reachable"]["status"] == "WARN"
    assert "不可达" in checks["itol_reachable"]["detail"]


def test_health_check_api_key_env_var(runtime: Runtime, monkeypatch) -> None:
    """设置 ITOL_API_KEY 环境变量 → api_key_configured=True。"""
    monkeypatch.setenv(KEY_ENV_VAR, "abcdef12345678")
    assert _api_key_configured(runtime) is True


def test_health_check_api_key_file_bad_perms(runtime: Runtime, monkeypatch) -> None:
    """密钥文件权限过宽 → api_key=WARN。"""
    kf = runtime.config.effective_key_file()
    kf.parent.mkdir(parents=True, exist_ok=True)
    kf.write_text("abcdef12345678\n", encoding="utf-8")
    import os

    os.chmod(kf, 0o644)
    res = _health_check_impl(runtime)
    checks = {c["name"]: c for c in res.data["checks"]}
    assert checks["api_key"]["status"] == "WARN"
    assert "权限过宽" in checks["api_key"]["detail"]


def test_health_check_api_key_file_ok_perms(runtime: Runtime, monkeypatch) -> None:
    """密钥文件权限 600 → api_key=OK。"""
    kf = runtime.config.effective_key_file()
    kf.parent.mkdir(parents=True, exist_ok=True)
    kf.write_text("abcdef12345678\n", encoding="utf-8")
    import os

    os.chmod(kf, 0o600)
    res = _health_check_impl(runtime)
    checks = {c["name"]: c for c in res.data["checks"]}
    assert checks["api_key"]["status"] == "OK"


# ---------------------------------------------------------------------------
# common 辅助扩展
# ---------------------------------------------------------------------------


def test_parse_json_invalid() -> None:
    with pytest.raises(UsageError, match="JSON"):
        parse_json("{bad json", "colors")


def test_parse_json_none_and_valid() -> None:
    assert parse_json(None) is None
    assert parse_json('{"a": 1}') == {"a": 1}


def test_table_to_rows_with_nan() -> None:
    rows = table_to_rows("id,v\na,\n")  # 空值 → NaN → None
    assert rows[0]["v"] is None


def test_table_to_rows_normal() -> None:
    rows = table_to_rows("id,v\na,1\nb,2.5\n")
    assert rows[0] == {"id": "a", "v": "1"}
    assert rows[1] == {"id": "b", "v": "2.5"}


def test_preview_lines_short() -> None:
    text = "line1\nline2"
    assert preview_lines(text, 5) == text


def test_preview_lines_truncated() -> None:
    text = "\n".join(f"line{i}" for i in range(50))
    result = preview_lines(text, 40)
    assert "共 50 行" in result
    assert result.count("\n") < 50


def test_runtime_client_required_false_no_key(runtime: Runtime) -> None:
    """无密钥且 required=False → 返回客户端而非抛错。"""
    client, source = runtime.client(required=False)
    assert client is not None
    assert source == ""


def test_server_info_env_key(runtime: Runtime, monkeypatch) -> None:
    """server_info 在设置 ITOL_API_KEY 环境变量后 api_key_configured=True。"""
    monkeypatch.setenv(KEY_ENV_VAR, "abcdef12345678")
    res = _server_info_impl(runtime)
    assert res.data["api_key_configured"] is True
