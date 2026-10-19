"""树服务测试：格式检测、解析错误、统计、输入校验矩阵。"""

from __future__ import annotations

import pytest

from itol_mcp.exceptions import TreeParseError
from itol_mcp.services.tree_service import (
    detect_format,
    parse_tree,
    summarize,
    validate_batch,
    validate_sequence_text,
    validate_taxonomy_text,
    validate_tree_text,
)
from itol_mcp.utils.constants import DISPLAY_MODES, EXPORT_FORMATS

NEWICK = "((A:0.1,B:0.2):0.3,C:0.4);"
NEXUS = """#NEXUS
BEGIN TREES;
TREE t1 = ((A,B),C);
END;
"""


def test_detect_formats() -> None:
    assert detect_format(NEWICK) == "newick"
    assert detect_format(NEXUS) == "nexus"
    with pytest.raises(TreeParseError, match="为空"):
        detect_format("   ")


def test_parse_tree_ok() -> None:
    tree = parse_tree(NEWICK)
    assert len(tree.leaf_nodes()) == 3


def test_parse_tree_invalid() -> None:
    with pytest.raises(TreeParseError, match="解析失败"):
        parse_tree("((A,B)")  # 括号不平衡


def test_summarize_stats() -> None:
    info = summarize(NEWICK)
    assert info.format == "newick"
    assert info.n_tips == 3
    assert info.n_internal == 2  # 根节点 + (A,B) 内节点
    assert info.n_nodes == 5
    assert info.has_branch_lengths is True
    assert info.tips == ["A", "B", "C"]
    assert info.total_branch_length is not None


def test_summarize_warns_missing_branch_lengths() -> None:
    info = summarize("((A,B),C);")
    assert any("分支长度" in w for w in info.warnings)


def test_summarize_duplicate_tips_raises_parse_error() -> None:
    # dendropy 默认将重复末端标签视为非法（iTOL 亦无法渲染），应抛解析错误
    with pytest.raises(TreeParseError, match="解析失败"):
        summarize("((A,A),B);")


def test_validate_tree_pass() -> None:
    checks = validate_tree_text(NEWICK)
    assert any(c["level"] == "PASS" for c in checks)


def test_validate_tree_negative_branch() -> None:
    checks = validate_tree_text("((A:-0.1,B:0.2),C);")
    assert any(c["level"] == "CRITICAL" and "负分支长度" in c["message"] for c in checks)


def test_validate_tree_unbalanced() -> None:
    checks = validate_tree_text("((A,B)")
    assert any(c["level"] == "CRITICAL" and "括号不平衡" in c["message"] for c in checks)


def test_validate_tree_multiroot() -> None:
    checks = validate_tree_text("(A,B);(C,D);")
    assert any("多个根" in c["message"] for c in checks)


def test_validate_tree_empty() -> None:
    checks = validate_tree_text("")
    assert checks[0]["level"] == "CRITICAL"


def test_validate_taxonomy_missing_id() -> None:
    checks = validate_taxonomy_text("x,y\n1,2\n")
    assert any(c["level"] == "CRITICAL" and "ID 列" in c["message"] for c in checks)


def test_validate_taxonomy_duplicate_warns() -> None:
    checks = validate_taxonomy_text("id,d\nA,x\nA,y\n")
    assert any(c["level"] == "WARN" and "重复" in c["message"] for c in checks)


def test_validate_sequence_dna_protein() -> None:
    dna = ">s1\nACGTACGT\n>s2\nACGTACGT\n"
    checks = validate_sequence_text(dna)
    assert any(c["level"] == "PASS" for c in checks)
    protein = ">p1\nMKTAYIAKQRQISFVKSHFSRQ\n"
    checks2 = validate_sequence_text(protein)
    assert any(c["level"] == "PASS" for c in checks2)


def test_validate_sequence_empty() -> None:
    checks = validate_sequence_text("")
    assert checks[0]["level"] == "CRITICAL"


def test_validate_batch_all_passed() -> None:
    result = validate_batch(tree_text=NEWICK, taxonomy_text="id,d\nA,x\n")
    assert result["all_passed"] is True
    assert set(result["checks"]) == {"tree", "taxonomy"}


def test_validate_batch_fail() -> None:
    result = validate_batch(tree_text="((A", taxonomy_text="id,d\nA,x\n")
    assert result["all_passed"] is False


def test_export_formats_cover_plan() -> None:
    assert "pdf" in EXPORT_FORMATS and "svg" in EXPORT_FORMATS and "newick" in EXPORT_FORMATS


def test_display_modes() -> None:
    assert DISPLAY_MODES[1] == "矩形"
    assert DISPLAY_MODES[2] == "环形"
