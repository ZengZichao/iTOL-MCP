"""工具函数测试：颜色、表格解析、数值格式化、脱敏、文件名消毒、模板类型注册表。"""

from __future__ import annotations

import pytest

from itol_mcp.exceptions import TemplateError, WorkspaceError
from itol_mcp.services.template_service import list_template_types
from itol_mcp.utils.color_tools import (
    PALETTES,
    assign_colors,
    build_category_color_map,
    validate_color,
)
from itol_mcp.utils.io import (
    atomic_write_text,
    detect_control_chars,
    format_number,
    parse_table_text,
    redact,
    safe_filename_part,
    translate_itol_api_error,
)
from itol_mcp.utils.logger import RedactingFilter, get_logger, setup_logging
from itol_mcp.utils.result import ToolResult, truncate_preview

# ---------------------------------------------------------------------------
# 颜色
# ---------------------------------------------------------------------------


def test_validate_color_normalizes() -> None:
    assert validate_color("#ff0000") == "#FF0000"
    assert validate_color("red") == "#FF0000"
    assert validate_color("#abc") == "#ABC"
    assert validate_color("#ff000088") == "#FF000088"


def test_validate_color_rejects() -> None:
    with pytest.raises(TemplateError, match="非法颜色"):
        validate_color("notacolor")
    with pytest.raises(TemplateError, match="不能为空"):
        validate_color("")


def test_assign_colors_palette_known() -> None:
    colors, warnings = assign_colors(["A", "B", "A"])
    assert len(colors) == 3
    assert colors[0] == colors[2]
    assert warnings == []


def test_assign_colors_unknown_palette() -> None:
    with pytest.raises(TemplateError, match="未知配色方案"):
        assign_colors(["A"], palette="bogus")


def test_assign_colors_overflow_warns() -> None:
    many = [f"cat{i}" for i in range(20)]
    _, warnings = assign_colors(many, palette="ibm")  # ibm 只有 5 色
    assert any("循环取色" in w for w in warnings)


def test_assign_colors_explicit() -> None:
    colors, _ = assign_colors(["A", "B"], explicit={"A": "#000000"})
    assert colors[0] == "#000000"
    assert colors[1].startswith("#")


def test_build_category_color_map() -> None:
    mapping, _ = build_category_color_map(["x", "y", "x"])
    assert mapping["x"] == mapping.get("x")
    assert len(mapping) == 2


def test_palettes_all_present() -> None:
    assert set(PALETTES) == {"tol_bright", "tol_vibrant", "wong", "okabeito", "ibm"}


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------


def test_format_number() -> None:
    assert format_number(3) == "3"
    assert format_number(3.140000) == "3.14"
    assert format_number(True) == "1"
    assert format_number(False) == "0"
    assert format_number("abc") == "abc"


def test_safe_filename_part() -> None:
    assert safe_filename_part("tree 123") == "tree_123"
    assert safe_filename_part("a.b-c_d") == "a.b-c_d"
    with pytest.raises(WorkspaceError, match="非法文件名"):
        safe_filename_part("...")  # 仅含点号 → 消毒后为空


def test_parse_table_text_tab_and_comma() -> None:
    df_tab = parse_table_text("id\td\nA\tx\n")
    assert list(df_tab.columns) == ["id", "d"]
    df_comma = parse_table_text("id,d\nA,x\n")
    assert list(df_comma.columns) == ["id", "d"]


def test_parse_table_text_comment() -> None:
    df = parse_table_text("# comment\nid,d\nA,x\n")
    assert len(df) == 1
    assert list(df.columns) == ["id", "d"]


def test_parse_table_text_empty() -> None:
    with pytest.raises(WorkspaceError, match="为空"):
        parse_table_text("   ")


def test_redact() -> None:
    text = "api_key=supersecret123 end"
    out = redact(text, secrets={"supersecret123"})
    assert "supersecret123" not in out
    assert "REDACTED" in out


def test_detect_control_chars() -> None:
    assert detect_control_chars("normal") == []
    assert len(detect_control_chars("a\x00b")) >= 1


def test_translate_itol_api_error() -> None:
    assert "订阅" in translate_itol_api_error("SUBSCRIPTION required")
    assert "API Key 无效" in translate_itol_api_error("ERR: INVALID API KEY")
    assert "不存在" in translate_itol_api_error("NOT FOUND")


def test_atomic_write_text(tmp_path) -> None:

    target = tmp_path / "sub" / "f.txt"
    atomic_write_text(target, "content")
    assert target.read_text(encoding="utf-8") == "content"
    with pytest.raises(WorkspaceError, match="已存在"):
        atomic_write_text(target, "again")


def test_read_text_file_unicode_error(tmp_path) -> None:
    from itol_mcp.utils.io import read_text_file

    p = tmp_path / "bin.txt"
    p.write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(WorkspaceError, match="UTF-8"):
        read_text_file(p)


def test_parse_table_text_comment_only() -> None:
    from itol_mcp.utils.io import parse_table_text

    with pytest.raises(WorkspaceError, match="无有效数据行"):
        parse_table_text("# comment only")


def test_parse_table_text_semicolon() -> None:
    """显式 sep=';' 时支持分号。"""
    df = parse_table_text("id;d\nA;x\n", sep=";")
    assert list(df.columns) == ["id", "d"]


def test_parse_table_text_bad_pandas(tmp_path) -> None:
    """pandas 解析失败 → WorkspaceError。"""
    from itol_mcp.utils.io import parse_table_text

    # 空列名等 pandas 无法处理的情况
    with pytest.raises(WorkspaceError, match=r"解析失败|没有有效"):
        parse_table_text("a,b\n1,2\n3,4,5\n")


def test_format_number_nan() -> None:
    assert format_number(float("nan")) == "0.0"


def test_translate_itol_api_error_empty() -> None:
    assert "空响应" in translate_itol_api_error("   ")


def test_translate_itol_api_error_ext() -> None:
    assert "格式" in translate_itol_api_error("BAD EXTENSION")
    assert "过大" in translate_itol_api_error("SIZE EXCEEDED")
    assert "繁忙" in translate_itol_api_error("SERVER BUSY")
    # 未知错误 → 原文返回
    assert translate_itol_api_error("UNKNOWN ERROR CODE") == "UNKNOWN ERROR CODE"


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------


def test_toolresult_ok_and_err() -> None:
    ok = ToolResult.ok("done", {"x": 1}, warnings=["w"])
    assert ok.success is True
    assert ok.to_dict() == {
        "success": True,
        "message": "done",
        "data": {"x": 1},
        "warnings": ["w"],
        "files": [],
    }
    err = ToolResult.err("boom")
    assert err.success is False
    assert err.message == "boom"


def test_truncate_preview() -> None:
    assert truncate_preview("short") == "short"
    assert len(truncate_preview("x" * 100, limit=10)) <= 10 + 20


# ---------------------------------------------------------------------------
# 模板注册表常量
# ---------------------------------------------------------------------------


def test_template_registry_unique_headers() -> None:
    types = list_template_types()
    headers = [t["header"] for t in types]
    assert len(set(headers)) == len(headers)


def test_template_registry_all_32_plus() -> None:
    assert len(list_template_types()) >= 32


# ---------------------------------------------------------------------------
# logger 测试
# ---------------------------------------------------------------------------


def test_redacting_filter_redacts_secrets() -> None:
    import logging

    flt = RedactingFilter(secrets={"supersecretkey"})
    rec = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1,
        msg="key=supersecretkey api_key=anotherkey123",
        args=(), exc_info=None,
    )
    assert flt.filter(rec)
    assert "***REDACTED***" in rec.getMessage()
    assert "supersecretkey" not in rec.getMessage()
    assert "anotherkey" not in rec.getMessage()


def test_redacting_filter_keeps_normal() -> None:
    import logging

    flt = RedactingFilter()
    rec = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1,
        msg="normal message", args=(), exc_info=None,
    )
    assert flt.filter(rec)
    assert rec.getMessage() == "normal message"


def test_setup_logging_idempotent_adds_secrets(tmp_path) -> None:
    """重复调用 setup_logging 时更新 secrets。"""
    logger1 = setup_logging(tmp_path / "logs", level="INFO", secrets={"secret1"})
    logger2 = setup_logging(tmp_path / "logs", level="DEBUG", secrets={"secret2"})
    assert logger1 is logger2
    # 找到过滤器并验证 secrets 合并
    for flt in logger1.filters:
        if isinstance(flt, RedactingFilter):
            assert "secret2" in flt.secrets
            break
    else:
        raise AssertionError("未找到 RedactingFilter")


def test_get_logger_returns_initialized() -> None:
    """setup_logging 后 get_logger 返回同一实例。"""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        logger = setup_logging(Path(td), level="INFO")
        assert get_logger() is logger
