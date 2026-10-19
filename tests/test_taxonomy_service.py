"""分类学服务测试：名称解析、单系性三分类、条件美化、分类学驱动着色。"""

from __future__ import annotations

import pytest

from itol_mcp.exceptions import TaxonomyError
from itol_mcp.services.taxonomy_service import (
    _resolve_rank_column,
    build_color_strip_rows,
    check_and_style,
    check_monophyly,
    extract_taxonomy_from_names,
    load_taxonomy_table,
    numeric_column_values,
    parse_embedded_name,
    parse_gtdb_name,
    parse_ncbi_name,
    summarize_monophyly,
)
from itol_mcp.utils.io import parse_table_text

# ---------------------------------------------------------------------------
# 名称分类学解析
# ---------------------------------------------------------------------------


def test_parse_gtdb_name() -> None:
    row = parse_gtdb_name(
        "d__Bacteria;p__Firmicutes;c__Bacilli;o__Bacillales;f__Bacillaceae;g__Bacillus;s__Bacillus_subtilis"
    )
    assert row["d"] == "Bacteria"
    assert row["p"] == "Firmicutes"
    assert row["s"] == "Bacillus_subtilis"
    assert row["source_format"] == "gtdb"


def test_parse_embedded_name() -> None:
    name = "GB_GCA_1_d_Bacteria_p_Firmicutes_c_Bacilli_o_Bacillales_f_Bacillaceae_g_Bacillus_s_Bacillus_subtilis"
    row = parse_embedded_name(name)
    assert row["d"] == "Bacteria"
    assert row["g"] == "Bacillus"
    assert row["s"] == "Bacillus_subtilis"
    assert row["source_format"] == "embedded"


def test_parse_ncbi_name() -> None:
    row = parse_ncbi_name("Escherichia_coli")
    assert row["g"] == "Escherichia"
    assert row["s"] == "coli"


def test_extract_from_embedded_names(tax130_text: str, tree130_text: str) -> None:
    rows = extract_taxonomy_from_names(tree130_text, fmt="auto")
    assert len(rows) == 130
    assert all(r["source_format"] == "embedded" for r in rows)
    assert all(r["d"] == "Bacteria" for r in rows)
    phyla = {r["p"] for r in rows}
    assert len(phyla) == 6  # 合成 130 末端数据共 6 个门


def test_extract_rejects_unknown_format() -> None:
    with pytest.raises(TaxonomyError, match="未知分类学格式"):
        extract_taxonomy_from_names("((A,B),C);", fmt="bogus")


# ---------------------------------------------------------------------------
# 表格加载与列解析
# ---------------------------------------------------------------------------


def test_load_taxonomy_short_and_full_columns(tax32_text: str, tax130_text: str) -> None:
    df_full = load_taxonomy_table(tax32_text)
    assert _resolve_rank_column(df_full, "Genus") == "Genus"
    df_short = load_taxonomy_table(tax130_text)
    assert _resolve_rank_column(df_short, "Genus") == "g"
    assert _resolve_rank_column(df_short, "Bogus") is None


def test_load_taxonomy_missing_id_column() -> None:
    with pytest.raises(TaxonomyError, match="ID 列"):
        load_taxonomy_table("x,y\n1,2\n")


# ---------------------------------------------------------------------------
# 单系性三分类（32 末端演示数据）
# ---------------------------------------------------------------------------


def test_monophyly_32_tips_summary(tree32_text: str, tax32_text: str) -> None:
    results = check_monophyly(tree32_text, tax32_text, rank="Genus")
    by_group = {r["group"]: r["status"] for r in results}
    assert by_group["GenusA"] == "mono"
    assert by_group["GenusB"] == "mono"
    assert by_group["GenusC"] == "mono"
    assert by_group["GenusD"] == "para"
    assert by_group["GenusE"] == "poly"
    assert by_group["GenusF"] == "mono"
    assert by_group["GenusG"] == "mono"
    assert summarize_monophyly(results) == {"mono": 5, "para": 1, "poly": 1, "absent": 0}


def test_monophyly_taxa_filter(tree32_text: str, tax32_text: str) -> None:
    results = check_monophyly(tree32_text, tax32_text, rank="Genus", taxa=["GenusD", "GenusA"])
    by_group = {r["group"]: r["status"] for r in results}
    assert by_group == {"GenusA": "mono", "GenusD": "para"}


def test_monophyly_unknown_rank(tree32_text: str, tax32_text: str) -> None:
    with pytest.raises(TaxonomyError, match="不支持的等级"):
        check_monophyly(tree32_text, tax32_text, rank="Spaghetti")


def test_monophyly_130_special_taxa(tree130_text: str, tax130_text: str) -> None:
    lbca = check_monophyly(tree130_text, tax130_text, rank="Domain", taxa=["LBCA"])[0]
    assert lbca["status"] == "mono"
    assert lbca["member_count"] == 130
    root = check_monophyly(tree130_text, tax130_text, rank="Domain", taxa=["ROOT"])[0]
    assert root["status"] == "mono"


def test_monophyly_membership_limit_caps_at_50(tree130_text: str, tax130_text: str) -> None:
    result_limited = check_monophyly(tree130_text, tax130_text, rank="Domain", taxa=["LBCA"])[0]
    assert len(result_limited["member_ids"]) == 50
    result_full = check_monophyly(
        tree130_text, tax130_text, rank="Domain", taxa=["LBCA"], _member_limit=None
    )[0]
    assert len(result_full["member_ids"]) == 130


def test_monophyly_absent_taxon(tree32_text: str, tax32_text: str) -> None:
    result = check_monophyly(tree32_text, tax32_text, rank="Genus", taxa=["GenusZ"])[0]
    assert result["status"] == "absent"


# ---------------------------------------------------------------------------
# 条件美化（check-and-style）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("action", "header", "needle"),
    [
        ("color_branch", "TREE_COLORS", "branch"),
        ("highlight", "TREE_COLORS", "label"),
        ("collapse", "COLLAPSE", "\t1"),
        ("color_strip", "DATASET_COLORSTRIP", "COLOR"),
    ],
)
def test_check_and_style_mono_applies(tree32_text, tax32_text, action, header, needle) -> None:
    result = check_and_style(
        tree32_text, tax32_text, taxon="GenusA", rank="Genus", action=action, color="#112233"
    )
    assert result["status"] == "mono"
    assert result["action_applied"] is True
    assert result["template"].startswith(header)
    assert needle in result["template"]
    assert result["group_info"]["member_ids"] == [f"A{i}" for i in range(1, 7)]


def test_check_and_style_para_skips(tree32_text: str, tax32_text: str) -> None:
    result = check_and_style(
        tree32_text, tax32_text, taxon="GenusD", rank="Genus", action="color_branch"
    )
    assert result["status"] == "para"
    assert result["action_applied"] is False
    assert "并系" in result["skipped_reason"]
    assert result["template"] is None


def test_check_and_style_poly_skips(tree32_text: str, tax32_text: str) -> None:
    result = check_and_style(
        tree32_text, tax32_text, taxon="GenusE", rank="Genus", action="highlight"
    )
    assert result["status"] == "poly"
    assert result["action_applied"] is False
    assert "复系" in result["skipped_reason"]


def test_check_and_style_strict_raises(tree32_text: str, tax32_text: str) -> None:
    with pytest.raises(TaxonomyError, match="strict"):
        check_and_style(
            tree32_text,
            tax32_text,
            taxon="GenusD",
            rank="Genus",
            action="color_branch",
            strict=True,
        )


def test_check_and_style_bad_action(tree32_text: str, tax32_text: str) -> None:
    with pytest.raises(TaxonomyError, match="未知美化操作"):
        check_and_style(tree32_text, tax32_text, taxon="GenusA", rank="Genus", action="explode")


# ---------------------------------------------------------------------------
# 分类学驱动着色 / 数值列
# ---------------------------------------------------------------------------


def test_build_color_strip_rows(tree32_text: str, tax32_text: str) -> None:
    from itol_mcp.services.tree_service import parse_tree

    rows, _warnings = build_color_strip_rows(tree32_text, tax32_text, "id", "Phylum", "tol_vibrant")
    tree_ids = {n.taxon.label for n in parse_tree(tree32_text).leaf_node_iter() if n.taxon}
    assert len(rows) == 32
    assert {r["id"] for r in rows} == tree_ids
    assert {r["value"] for r in rows} == {"Pseudomonadota"}
    colors = {r["color"] for r in rows}
    assert len(colors) == 1 and next(iter(colors)).startswith("#")


def test_build_color_strip_missing_column(tree32_text: str, tax32_text: str) -> None:
    with pytest.raises(TaxonomyError, match="缺少列"):
        build_color_strip_rows(tree32_text, tax32_text, "id", "nope")


def test_numeric_column_values(tax130_text: str) -> None:
    values = numeric_column_values("", tax130_text, "id", "g")
    assert len(values) == 130
    assert all(isinstance(v, float) for _, v in values)


def test_numeric_column_non_numeric_zero() -> None:
    text = "id,d\nA,abc\nB,12.5\n"
    values = numeric_column_values("", text, "id", "d")
    assert values == [("A", 0.0), ("B", 12.5)]


def test_parse_table_text_roundtrip() -> None:
    df = parse_table_text("id,d\nA,x\nB,y\n")
    assert list(df.columns) == ["id", "d"]
    assert len(df) == 2
