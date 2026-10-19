"""树分析与分类学工具层测试（直接调用 *_impl 函数）。

覆盖：itol_tree_info、itol_validate_inputs、itol_taxonomy_extract、itol_taxonomy_monophyly、itol_taxonomy_check_and_style。
"""

from __future__ import annotations

import pytest

from itol_mcp.exceptions import UsageError
from itol_mcp.tools.common import Runtime
from itol_mcp.tools.taxonomy_tools import (
    _check_and_style_impl,
    _monophyly_impl,
    _taxonomy_extract_impl,
)
from itol_mcp.tools.tree_tools import _tree_info_impl, _validate_inputs_impl

NEWICK = "((A:0.1,B:0.2):0.3,C:0.4);"
TAX = "id,d\nA,Bacteria\nB,Bacteria\nC,Bacteria\n"


# ---------------------------------------------------------------------------
# 树分析工具
# ---------------------------------------------------------------------------


def test_tree_info_impl_inline(runtime: Runtime) -> None:
    res = _tree_info_impl(runtime, NEWICK, None)
    assert res.success is True
    assert res.data["n_tips"] == 3
    assert res.data["format"] == "newick"


def test_tree_info_impl_from_file(runtime: Runtime) -> None:
    runtime.workspace.write_text("data/t.nwk", NEWICK)
    res = _tree_info_impl(runtime, None, "data/t.nwk")
    assert res.success is True
    assert res.data["n_tips"] == 3


def test_tree_info_impl_mutual_exclusion(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="互斥"):
        _tree_info_impl(runtime, NEWICK, "data/t.nwk")


def test_tree_info_impl_missing(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="至少需要"):
        _tree_info_impl(runtime, None, None)


def test_validate_inputs_all_pass(runtime: Runtime) -> None:
    res = _validate_inputs_impl(runtime, NEWICK, None, TAX, None, None, None, "auto", "id")
    assert res.success is True
    assert res.data["all_passed"] is True
    assert set(res.data["checks"]) == {"tree", "taxonomy"}


def test_validate_inputs_requires_one(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="至少需要提供一类输入"):
        _validate_inputs_impl(runtime, None, None, None, None, None, None, "auto", "id")


def test_validate_inputs_sequence(runtime: Runtime) -> None:
    seq = ">s1\nACGTACGT\n"
    res = _validate_inputs_impl(runtime, None, None, None, None, seq, None, "dna", "id")
    assert res.success is True


# ---------------------------------------------------------------------------
# 分类学提取工具
# ---------------------------------------------------------------------------


def test_taxonomy_extract_from_tree(runtime: Runtime, tree130_text: str) -> None:
    res = _taxonomy_extract_impl(runtime, tree130_text, None, None, None, "auto", None, None)
    assert res.success is True
    assert res.data["n_rows"] == 130
    assert res.data["source_format_detected"] == "embedded"
    assert "d" in res.data["columns"]


def test_taxonomy_extract_from_table(runtime: Runtime, tax32_text: str) -> None:
    res = _taxonomy_extract_impl(runtime, None, None, tax32_text, None, "auto", None, None)
    assert res.success is True
    assert res.data["source_format_detected"] == "table"
    assert res.data["n_rows"] >= 32


def test_taxonomy_extract_missing_both(runtime: Runtime) -> None:
    with pytest.raises(UsageError, match="需要提供来源"):
        _taxonomy_extract_impl(runtime, None, None, None, None, "auto", None, None)


def test_taxonomy_extract_mutual_exclusion(
    runtime: Runtime, tree130_text: str, tax32_text: str
) -> None:
    with pytest.raises(UsageError, match="互斥"):
        _taxonomy_extract_impl(runtime, tree130_text, None, tax32_text, None, "auto", None, None)


def test_taxonomy_extract_to_output(runtime: Runtime, tree130_text: str) -> None:
    res = _taxonomy_extract_impl(
        runtime, tree130_text, None, None, None, "auto", None, "data/tax.csv"
    )
    assert res.success is True
    assert res.data["output_file"] is not None
    content = runtime.workspace.read_text("data/tax.csv")
    assert "d,p" in content or "d," in content


# ---------------------------------------------------------------------------
# 单系性工具
# ---------------------------------------------------------------------------


def test_monophyly_impl_rank_required(runtime: Runtime, tree32_text: str, tax32_text: str) -> None:
    with pytest.raises(UsageError, match="rank 必填"):
        _monophyly_impl(runtime, tree32_text, None, tax32_text, None, "", None, None)


def test_monophyly_impl_summary(runtime: Runtime, tree32_text: str, tax32_text: str) -> None:
    res = _monophyly_impl(runtime, tree32_text, None, tax32_text, None, "Genus", None, None)
    assert res.success is True
    assert res.data["summary"] == {"mono": 5, "para": 1, "poly": 1, "absent": 0}
    assert res.data["n_checked"] == 7


def test_monophyly_impl_output(runtime: Runtime, tree32_text: str, tax32_text: str) -> None:
    res = _monophyly_impl(
        runtime, tree32_text, None, tax32_text, None, "Genus", "GenusA", "data/mono.csv"
    )
    assert res.success is True
    assert res.data["output_file"] is not None
    assert runtime.workspace.read_text("data/mono.csv").startswith("group,rank")


# ---------------------------------------------------------------------------
# check-and-style 工具
# ---------------------------------------------------------------------------


def test_check_and_style_mono(runtime: Runtime, tree32_text: str, tax32_text: str) -> None:
    res = _check_and_style_impl(
        runtime,
        tree32_text,
        None,
        tax32_text,
        None,
        "GenusA",
        "Genus",
        "color_branch",
        "#112233",
        False,
        None,
    )
    assert res.success is True
    assert res.data["status"] == "mono"
    assert res.data["action_applied"] is True
    assert res.data["template_header"] == "TREE_COLORS"


def test_check_and_style_auto_taxonomy(runtime: Runtime) -> None:
    # 树末端名含嵌入式 GTDB 分类学，不提供分类表时应自动提取
    embedded = (
        "((('x_d_Bacteria_p_Firmicutes_g_GenusX_s_X_a1':0.1,"
        "'y_d_Bacteria_p_Firmicutes_g_GenusX_s_X_a2':0.1):0.05),"
        "'z_d_Bacteria_p_Firmicutes_g_GenusY_s_Y_b1':0.1);"
    )
    res = _check_and_style_impl(
        runtime,
        embedded,
        None,
        None,
        None,
        "GenusX",
        "Genus",
        "color_strip",
        "#112233",
        False,
        None,
    )
    assert res.success is True
    assert res.data["status"] == "mono"
    assert res.data["action_applied"] is True
    assert res.data["template_header"] == "DATASET_COLORSTRIP"


def test_check_and_style_para_skip(runtime: Runtime, tree32_text: str, tax32_text: str) -> None:
    res = _check_and_style_impl(
        runtime,
        tree32_text,
        None,
        tax32_text,
        None,
        "GenusD",
        "Genus",
        "color_branch",
        "#112233",
        False,
        None,
    )
    assert res.data["status"] == "para"
    assert res.data["action_applied"] is False


def test_check_and_style_strict_raises(runtime: Runtime, tree32_text: str, tax32_text: str) -> None:
    with pytest.raises(Exception, match="strict"):
        _check_and_style_impl(
            runtime,
            tree32_text,
            None,
            tax32_text,
            None,
            "GenusD",
            "Genus",
            "color_branch",
            "#112233",
            True,
            None,
        )


def test_check_and_style_requires_taxon(
    runtime: Runtime, tree32_text: str, tax32_text: str
) -> None:
    with pytest.raises(UsageError, match="taxon 必填"):
        _check_and_style_impl(
            runtime,
            tree32_text,
            None,
            tax32_text,
            None,
            "",
            "Genus",
            "color_branch",
            "#112233",
            False,
            None,
        )
