"""模板工具层测试（直接调用 *_impl 函数）。

覆盖：统一入口、快捷入口（color_strip/heatmap/simple_bar/multi_bar/binary/gradient/symbols/pie_chart/connections/domains/boxplot/tree_ops）、bundle、validate。
"""

from __future__ import annotations

import pytest

from itol_mcp.exceptions import UsageError
from itol_mcp.tools.common import Runtime
from itol_mcp.tools.template_tools import (
    _binary_impl,
    _boxplot_impl,
    _bundle_impl,
    _color_strip_impl,
    _connections_impl,
    _domains_impl,
    _gradient_impl,
    _heatmap_impl,
    _multi_bar_impl,
    _pie_chart_impl,
    _simple_bar_impl,
    _symbols_impl,
    _template_create_impl,
    _template_types_impl,
    _tree_ops_impl,
    _validate_impl,
)
from itol_mcp.utils.result import ToolResult


def _read_result(runtime: Runtime, res: ToolResult | dict) -> str:
    data = res.data if isinstance(res, ToolResult) else res["data"]
    path = data["output"]
    return (runtime.workspace.root / path).resolve().read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------


def test_template_types_impl_all_and_single() -> None:
    res = _template_types_impl(None)
    assert res.success is True
    assert res.data["total"] >= 32
    single = _template_types_impl("color_strip")
    assert single.data["total"] == 1
    assert single.data["types"][0]["type_name"] == "color_strip"


def test_template_create_missing_type(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="template_type 必填"):
        _template_create_impl(
            runtime,
            "",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "#ff0000",
            "TAB",
            None,
            None,
            None,
            None,
            False,
            "id",
        )


def test_template_create_data_rows(runtime: Runtime) -> None:
    res = _template_create_impl(
        runtime,
        "color_strip",
        [{"id": "A", "value": "x"}],
        None,
        None,
        None,
        None,
        None,
        None,
        "s",
        "#ff0000",
        "TAB",
        None,
        None,
        None,
        None,
        False,
        "id",
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert text.startswith("DATASET_COLORSTRIP")
    assert "A\tx\t#FF0000" in text


def test_template_create_taxonomy_driven(
    runtime: Runtime, tree32_text: str, tax32_text: str
) -> None:
    runtime.workspace.write_text("data/t.nwk", tree32_text)
    runtime.workspace.write_text("data/tax.csv", tax32_text)
    res = _template_create_impl(
        runtime,
        "color_strip",
        None,
        None,
        None,
        "data/t.nwk",
        None,
        "data/tax.csv",
        "Phylum",
        "phylum",
        "#ff0000",
        "TAB",
        "wong",
        None,
        None,
        None,
        False,
        "id",
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "DATASET_COLORSTRIP" in text
    assert "Pseudomonadota" in text


def test_template_create_multiple_sources_rejected(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="互斥"):
        _template_create_impl(
            runtime,
            "color_strip",
            [{"id": "A"}],
            "data/t.csv",
            "((A,B),C);",
            None,
            "id,v\nA,1\n",
            None,
            "v",
            None,
            "#ff0000",
            "TAB",
            None,
            None,
            None,
            None,
            False,
            "id",
        )


# ---------------------------------------------------------------------------
# 快捷入口
# ---------------------------------------------------------------------------


def test_color_strip_data_rows(runtime: Runtime) -> None:
    res = _color_strip_impl(
        runtime,
        None,
        None,
        None,
        None,
        None,
        [{"id": "A", "value": "x"}, {"id": "B", "value": "y"}],
        "cs",
        None,
        None,
        50,
        None,
        None,
        False,
        "id",
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\tx\t#" in text
    assert "STRIP_WIDTH 50" in text


def test_color_strip_no_source(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="color_strip 需要数据来源"):
        _color_strip_impl(
            runtime,
            None,
            None,
            None,
            None,
            None,
            None,
            "cs",
            None,
            None,
            50,
            None,
            None,
            False,
            "id",
        )


def test_heatmap_requires_columns(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="columns 必填"):
        _heatmap_impl(runtime, [{"id": "A", "v1": 1}], None, "", None, None, None, False)


def test_heatmap_impl(runtime: Runtime) -> None:
    res = _heatmap_impl(
        runtime,
        [{"id": "A", "v1": 1.5, "v2": 2.0}],
        None,
        "v1,v2",
        "#ff0000,#0000ff",
        {"WIDTH": 200},
        None,
        False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert text.startswith("DATASET_HEATMAP")
    assert "GRADIENT #ff0000,#0000ff" in text
    assert "A\t1.5\t2" in text


def test_simple_bar_impl(runtime: Runtime) -> None:
    res = _simple_bar_impl(
        runtime, [{"id": "A", "value": 3.14}], None, "value", "#3c5484", 50, None, None, False
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert text.startswith("DATASET_SIMPLEBAR")
    assert "A\t3.14" in text


def test_simple_bar_requires_column(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="column 必填"):
        _simple_bar_impl(
            runtime, [{"id": "A", "value": 1}], None, "", "#3c5484", 50, None, None, False
        )


def test_multi_bar_impl(runtime: Runtime) -> None:
    res = _multi_bar_impl(
        runtime,
        [{"id": "A", "c1": 1, "c2": 2}],
        None,
        "c1,c2",
        "x,y",
        '["#aa0000","#00aa00"]',
        1000,
        "center",
        None,
        None,
        False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\t1\t2" in text
    assert "FIELD_LABELS x,y" in text


def test_multi_bar_bad_alignment(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="alignment"):
        _multi_bar_impl(
            runtime, [{"id": "A", "c1": 1}], None, "c1", None, None, 1000, "diag", None, None, False
        )


def test_binary_impl(runtime: Runtime) -> None:
    res = _binary_impl(
        runtime,
        [{"id": "A", "p": 1, "n": 0}],
        None,
        "p,n",
        '["#ffffff","#000000"]',
        None,
        None,
        False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\t1\t0" in text


def test_gradient_impl(runtime: Runtime) -> None:
    res = _gradient_impl(
        runtime,
        [{"id": "A", "value": 50}],
        None,
        "value",
        "#ff0000",
        "#0000ff",
        True,
        "#ffff00",
        25,
        None,
        None,
        False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "COLOR_MIN #FF0000" in text
    assert "USE_MID_COLOR 1" in text


def test_symbols_impl(runtime: Runtime) -> None:
    res = _symbols_impl(
        runtime, [{"id": "A", "cat": "x"}], None, "cat", "circle", None, 30, 0, None, None, False
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert text.startswith("DATASET_SYMBOL")
    assert "A\t2\t1\t#" in text


def test_symbols_bad_type(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="symbol_type"):
        _symbols_impl(
            runtime,
            [{"id": "A", "cat": "x"}],
            None,
            "cat",
            "hexagon",
            None,
            30,
            0,
            None,
            None,
            False,
        )


def test_pie_chart_impl(runtime: Runtime) -> None:
    res = _pie_chart_impl(
        runtime, [{"id": "A", "s1": 10, "s2": 20}], None, "s1,s2", None, 50, None, None, False
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\t10\t20" in text


def test_connections_impl(runtime: Runtime) -> None:
    res = _connections_impl(
        runtime, [{"source1": "A", "source2": "B", "width": 2}], None, None, False
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\tB\t2" in text


def test_connections_requires(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="connections 必填"):
        _connections_impl(runtime, None, None, None, False)


def test_domains_impl(runtime: Runtime) -> None:
    res = _domains_impl(
        runtime, [{"id": "A", "type": "kin", "start": 1, "end": 10}], None, None, None, False
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\t1\t10\tkin" in text


def test_domains_requires_rows(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="data_rows 必填"):
        _domains_impl(runtime, None, None, None, None, False)


def test_boxplot_impl(runtime: Runtime) -> None:
    res = _boxplot_impl(
        runtime,
        [{"id": "A", "min": 1, "q1": 2, "med": 3, "q3": 4, "max": 5, "ex": 6}],
        None,
        "min",
        "q1",
        "med",
        "q3",
        "max",
        "ex",
        "#00ff00",
        1500,
        None,
        None,
        False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\t1\t2\t3\t4\t5\t6" in text


def test_boxplot_requires_five(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="min 必填"):
        _boxplot_impl(
            runtime,
            [{"id": "A"}],
            None,
            "",
            "q1",
            "med",
            "q3",
            "max",
            None,
            "#00ff00",
            1500,
            None,
            None,
            False,
        )


def test_tree_ops_collapse(runtime: Runtime) -> None:
    res = _tree_ops_impl(runtime, "collapse", [{"id": "A"}], None, None, None, False)
    text = _read_result(runtime, res)
    assert text.startswith("COLLAPSE")
    assert "A\t1" in text


def test_tree_ops_bad_kind(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="kind 可选"):
        _tree_ops_impl(runtime, "explode", [{"id": "A"}], None, None, None, False)


def test_bundle_impl(runtime: Runtime) -> None:
    res = _bundle_impl(
        runtime,
        [
            {"template_type": "color_strip", "data_rows": [{"id": "A", "value": "x"}]},
            {"template_type": "simple_bar", "data_rows": [{"id": "A", "value": 1}]},
        ],
        "fig2",
        None,
        None,
        None,
        None,
    )
    assert res.success is True
    assert res.data["n_templates"] == 2
    for f in res.data["files"]:
        assert "/fig2/" in f


def test_bundle_requires_specs(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="specs 必填"):
        _bundle_impl(runtime, None, "b", None, None, None, None)


def test_validate_impl(runtime: Runtime) -> None:
    res = _validate_impl(
        runtime, "DATASET_COLORSTRIP\nSEPARATOR TAB\nDATA\nA\tx\t#ff0000\n", None, None, None
    )
    assert res.success is True
    assert res.data["valid"] is True
    assert res.data["header"] == "DATASET_COLORSTRIP"


def test_validate_impl_requires_template(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="至少需要"):
        _validate_impl(runtime, None, None, None, None)


# ---------------------------------------------------------------------------
# 边缘路径补充
# ---------------------------------------------------------------------------


def test_color_strip_explicit_colors(runtime: Runtime) -> None:
    """data_rows + colors 显式映射 → 行颜色按映射补全。"""
    res = _color_strip_impl(
        runtime,
        None, None, None, None, None,
        [{"id": "A", "value": "x"}],
        "cs", '{"x": "#123456"}', None,
        50, None, None, False, "id",
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\tx\t#123456" in text


def test_color_strip_palette_auto(runtime: Runtime) -> None:
    """无 colors、无 color 字段 → 自动 palette 取色。"""
    res = _color_strip_impl(
        runtime,
        None, None, None, None, None,
        [{"id": "A", "value": "x"}, {"id": "B", "value": "y"}],
        "cs", None, "wong",
        50, None, None, False, "id",
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\tx\t#" in text
    assert "B\ty\t#" in text


def test_template_create_explicit_colors(runtime: Runtime) -> None:
    """统一入口传入 colors 映射。"""
    res = _template_create_impl(
        runtime,
        "color_strip",
        [{"id": "A", "value": "x"}],
        None, None, None, None, None, None,
        None, "#ff0000", "TAB", None,
        '{"x": "#00ff00"}',
        None, None, False, "id",
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\tx\t#00FF00" in text


def test_connections_with_options(runtime: Runtime) -> None:
    """connections 行带 color/width/line_type。"""
    res = _connections_impl(
        runtime,
        [
            {"source1": "A", "source2": "B", "color": "#aa0000", "width": 3, "line_type": "straight"},
            {"id1": "C", "id2": "D", "line_type": "solid"},
        ],
        None, None, False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\tB\t#AA0000\t3\t2" in text
    assert "C\tD\t#FF0000\t\t1" in text


def test_connections_missing_source(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="source1"):
        _connections_impl(runtime, [{"source1": "", "source2": "B"}], None, None, False)


def test_domains_with_color_map(runtime: Runtime) -> None:
    """domain_colors JSON 映射 → 行颜色补全。"""
    res = _domains_impl(
        runtime,
        [{"id": "A", "type": "kin", "start": 1, "end": 10}],
        '{"kin": "#aa00bb"}',
        None, None, False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\t1\t10\t#AA00BB" in text


def test_domains_bad_color_map(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="domain_colors"):
        _domains_impl(runtime, [{"id": "A", "type": "kin", "start": 1, "end": 2}], "[1,2]", None, None, False)


def test_domains_missing_from_to(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="from/start"):
        _domains_impl(runtime, [{"id": "A", "type": "kin"}], None, None, None, False)


def test_domains_from_to_alias(runtime: Runtime) -> None:
    """使用 from/to 别名键。"""
    res = _domains_impl(
        runtime,
        [{"id": "A", "type": "x", "from": 1, "to": 5, "color": "#ff0000"}],
        None, None, None, False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\t1\t5\t#FF0000" in text


def test_tree_ops_prune(runtime: Runtime) -> None:
    res = _tree_ops_impl(runtime, "prune", [{"id": "A"}], None, None, None, False)
    text = _read_result(runtime, res)
    assert text.startswith("PRUNE")
    assert "A" in text


def test_tree_ops_spacing(runtime: Runtime) -> None:
    res = _tree_ops_impl(runtime, "spacing", [{"id": "A", "space": 2.5}], None, None, None, False)
    text = _read_result(runtime, res)
    assert text.startswith("SPACING")
    assert "A\t2.5" in text


def test_tree_ops_treestyle(runtime: Runtime) -> None:
    res = _tree_ops_impl(
        runtime,
        "treestyle",
        [{"id": "A", "style": "bold", "width": 3, "color": "#00ff00"}],
        None, None, None, False,
    )
    text = _read_result(runtime, res)
    assert text.startswith("DATASET_TREESTYLE")
    assert "A\t#00FF00\t3" in text or "A" in text


def test_tree_ops_requires_rows(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="data_rows"):
        _tree_ops_impl(runtime, "prune", None, None, None, None, False)


def test_tree_ops_missing_id(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="id"):
        _tree_ops_impl(runtime, "prune", [{"foo": "bar"}], None, None, None, False)


def test_tree_ops_with_tree_validation(runtime: Runtime) -> None:
    """提供 tree → 校验 ID 匹配（不匹配产生警告）。"""
    res = _tree_ops_impl(
        runtime, "collapse", [{"id": "NOMATCH"}], None,
        "((A,B),C);", None, False,
    )
    assert res.success is True
    assert any("不匹配" in w for w in res.warnings)


def test_bundle_with_shared_tree_taxonomy(
    runtime: Runtime, tree32_text: str, tax32_text: str
) -> None:
    """bundle 内使用共享 tree/taxonomy 驱动。"""
    res = _bundle_impl(
        runtime,
        [{"template_type": "color_strip", "column": "Phylum"}],
        "shared",
        None, tree32_text, None, tax32_text,
    )
    assert res.success is True
    assert res.data["n_templates"] == 1


def test_bundle_missing_template_type(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="template_type"):
        _bundle_impl(runtime, [{"data_rows": []}], "b", None, None, None, None)


def test_bundle_table_file(runtime: Runtime) -> None:
    """bundle 规格内使用 table_file。"""
    runtime.workspace.write_text("data/t.csv", "id,value\nA,1\nB,2\n")
    res = _bundle_impl(
        runtime,
        [{"template_type": "simple_bar", "table_file": "data/t.csv", "column": "value"}],
        "bt",
        None, None, None, None,
    )
    assert res.success is True
    assert res.data["n_templates"] == 1


def test_multi_bar_dict_colors(runtime: Runtime) -> None:
    """multi_bar colors 传 JSON 对象。"""
    res = _multi_bar_impl(
        runtime,
        [{"id": "A", "c1": 1, "c2": 2}],
        None, "c1,c2", None,
        '{"c1": "#111111", "c2": "#222222"}',
        1000, "center", None, None, False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "COLORS #111111,#222222" in text


def test_gradient_with_mid_color(runtime: Runtime) -> None:
    """gradient use_mid_color=True。"""
    res = _gradient_impl(
        runtime,
        [{"id": "A", "value": 50}],
        None, "value", "#ff0000", "#0000ff", True, "#00ff00", 25, None, None, False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "USE_MID_COLOR 1" in text
    assert "COLOR_MID #00FF00" in text


def test_gradient_normalize_large_value(runtime: Runtime) -> None:
    """数值 >1 时归一化到 0-1。"""
    res = _gradient_impl(
        runtime,
        [{"id": "A", "value": 150}],
        None, "value", "#ff0000", "#0000ff", False, "#ffff00", 25, None, None, False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\t1" in text  # 150/100 = 1.5 → 归一化为 1.0 → "1"


def test_symbols_numeric_column(runtime: Runtime) -> None:
    """symbols 数值列 → 数值 value + 默认灰色。"""
    res = _symbols_impl(
        runtime,
        [{"id": "A", "cat": "3.14"}],
        None, "cat", "square", None, 30, 0, None, None, False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\t1\t3.14\t#999999" in text


def test_symbols_dict_colors(runtime: Runtime) -> None:
    """symbols colors 传 JSON 映射。"""
    res = _symbols_impl(
        runtime,
        [{"id": "A", "cat": "x"}],
        None, "cat", "star", '{"x": "#abcdef"}', 30, 0, None, None, False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "#ABCDEF" in text


def test_binary_with_colors(runtime: Runtime) -> None:
    """binary colors JSON 数组。"""
    res = _binary_impl(
        runtime,
        [{"id": "A", "p": 1, "n": 0}],
        None, "p,n", '["#ffffff","#000000"]', None, None, False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "COLORS #ffffff,#000000" in text


def test_boxplot_with_extremes(runtime: Runtime) -> None:
    """boxplot 带 extremes 列。"""
    res = _boxplot_impl(
        runtime,
        [{"id": "A", "min": 1, "q1": 2, "med": 3, "q3": 4, "max": 5, "ex1": 0, "ex2": 9}],
        None, "min", "q1", "med", "q3", "max", "ex1,ex2",
        "#00ff00", 1500, None, None, False,
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "A\t1\t2\t3\t4\t5\t0\t9" in text


def test_validate_with_tree(runtime: Runtime) -> None:
    """validate 传入 tree 做 ID 匹配。"""
    res = _validate_impl(
        runtime,
        "DATASET_COLORSTRIP\nSEPARATOR TAB\nDATA\nA\tx\t#ff0000\n",
        None,
        "((A,B),C);",
        None,
    )
    assert res.success is True
    assert "matched_ids" in res.data
    assert res.data["matched_ids"] == 1


def test_color_strip_taxonomy_driven(runtime: Runtime, tree32_text: str, tax32_text: str) -> None:
    """color_strip 快捷入口分类学驱动。"""
    runtime.workspace.write_text("data/t.nwk", tree32_text)
    runtime.workspace.write_text("data/tax.csv", tax32_text)
    res = _color_strip_impl(
        runtime,
        "data/t.nwk", None, "data/tax.csv", None,
        "Phylum", None,
        "cs", None, "wong",
        50, None, None, False, "id",
    )
    assert res.success is True
    text = _read_result(runtime, res)
    assert "DATASET_COLORSTRIP" in text
    assert "Pseudomonadota" in text
