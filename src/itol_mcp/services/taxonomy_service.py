"""分类学服务：名称分类学解析、分类表加载、单系群判定、条件美化（实现设计第 5.5 节）。

- 名称解析：GTDB（``d__…;p__…``）、嵌入式（``GB_…_d_Bacteria_p_…``）、
  NCBI（``Genus_species``）、auto 自动嗅探、mixed 混合；
- 单系群判定：基于 dendropy 的 MRCA 三分类（mono/para/poly）；
- 特殊标识符：LUCA / LACA / LBCA / ROOT。
"""

from __future__ import annotations

import re
from typing import Any

import dendropy
import pandas as pd

from itol_mcp.exceptions import TaxonomyError
from itol_mcp.services.tree_service import parse_tree
from itol_mcp.utils.constants import MONOPHYLY_ACTIONS, TREE_META_TAXA
from itol_mcp.utils.io import parse_table_text

# 等级 → 简写列（配置列）
RANK_COLUMNS: dict[str, str] = {
    "Domain": "d",
    "Phylum": "p",
    "Class": "c",
    "Order": "o",
    "Family": "f",
    "Genus": "g",
}

TAXONOMY_LEVELS = ("d", "p", "c", "o", "f", "g", "s")

_EMBEDDED_RE = re.compile(r"_(d|p|c|o|f|g|s)_+([A-Za-z0-9_\-\.]+?)(?=_+(?:d|p|c|o|f|g|s)_+|$)")
_GTDB_RE = re.compile(r"(d|p|c|o|f|g|s)__([^;]*)")
_SPECIES_SUFFIX_RE = re.compile(r"(.*?)\.?_([^_]+)_([^_]+)$")


# ---------------------------------------------------------------------------
# 名称分类学解析
# ---------------------------------------------------------------------------


def _empty_row(name: str) -> dict[str, str]:
    return {
        "name": name,
        "d": "",
        "p": "",
        "c": "",
        "o": "",
        "f": "",
        "g": "",
        "s": "",
        "source_format": "",
    }


def parse_gtdb_name(name: str) -> dict[str, str]:
    """解析 GTDB 分号式分类学：``d__Bacteria;p__Firmicutes;...``。"""
    row = _empty_row(name)
    row["source_format"] = "gtdb"
    for m in _GTDB_RE.finditer(name):
        key, value = m.group(1), m.group(2).strip()
        if key in row:
            row[key] = value
    return row


def parse_embedded_name(name: str) -> dict[str, str]:
    """解析嵌入式分类学：``GB_..._d_Bacteria_p_Firmicutes_...``。"""
    row = _empty_row(name)
    row["source_format"] = "embedded"
    for m in _EMBEDDED_RE.finditer(name):
        key, value = m.group(1), m.group(2).rstrip("_")
        if key in row:
            row[key] = value
    # 嵌入式通常没有 s__；NCBI 风格属种从尾部推断
    if not row["s"] and not row["g"]:
        tail = name.rstrip("_")
        parts = tail.split("_")
        if len(parts) >= 2 and row["g"]:
            row["s"] = parts[-1]
    return row


def parse_ncbi_name(name: str) -> dict[str, str]:
    """解析 NCBI 双名法：``Genus_species`` 或在名称尾部追加 ``g__Genus;s__Species``。"""
    row = _empty_row(name)
    row["source_format"] = "ncbi"
    gtdb_tail = _GTDB_RE.findall(name)
    for key, value in gtdb_tail:
        if key in row:
            row[key] = value.strip()
    if row["g"] or row["s"]:
        return row
    m = _SPECIES_SUFFIX_RE.search(name)
    if m:
        row["g"], row["s"] = m.group(2), m.group(3)
    else:
        parts = name.split("_")
        if len(parts) >= 2:
            row["g"], row["s"] = parts[-2], parts[-1]
        elif len(parts) == 1 and name:
            row["g"] = parts[0]
    return row


def sniff_name_format(name: str) -> str:
    """嗅探单条名称的分类学格式。"""
    if ";" in name and any(f"{rank}__" in name for rank in ("d", "p", "c", "o", "f", "g", "s")):
        return "gtdb"
    if re.search(r"_(d|p|c|o|f|g|s)__?[A-Za-z]", name):
        return "embedded"
    if re.search(r"^[A-Za-z][A-Za-z0-9\-]*_[A-Za-z_]+$", name) or ("_g_" in name or "_s_" in name):
        return "ncbi"
    return "unknown"


def extract_taxonomy_from_names(
    tree_text: str,
    fmt: str = "auto",
    taxonomy_levels: dict | None = None,
) -> list[dict[str, str]]:
    """从树末端名称提取分类学信息。

    ``fmt``：``gtdb`` / ``embedded`` / ``ncbi`` / ``auto`` / ``mixed``。
    返回行：``[{name, d, p, c, o, f, g, s, source_format}]``。
    """
    if fmt not in ("gtdb", "embedded", "ncbi", "auto", "mixed"):
        raise TaxonomyError(f"未知分类学格式：{fmt}（可选 gtdb/embedded/ncbi/auto/mixed）")
    tree = parse_tree(tree_text)
    names = [node.taxon.label for node in tree.leaf_node_iter() if node.taxon and node.taxon.label]

    effective = fmt
    if fmt in ("auto", "mixed"):
        sniffed = [sniff_name_format(n) for n in names]
        counts: dict[str, int] = {}
        for s in sniffed:
            counts[s] = counts.get(s, 0) + 1
        dominant = max(counts, key=lambda k: counts[k]) if counts else "unknown"
        if fmt == "auto" and dominant != "unknown":
            effective = dominant
        elif fmt == "auto":
            effective = "gtdb"
        else:  # mixed：逐行嗅探
            effective = "mixed"

    rows: list[dict[str, str]] = []
    for name in names:
        if effective == "gtdb":
            row = parse_gtdb_name(name)
        elif effective == "embedded":
            row = parse_embedded_name(name)
        elif effective == "ncbi":
            row = parse_ncbi_name(name)
        elif effective == "mixed":
            fmt2 = sniff_name_format(name)
            if fmt2 == "gtdb":
                row = parse_gtdb_name(name)
            elif fmt2 == "embedded":
                row = parse_embedded_name(name)
            elif fmt2 == "ncbi":
                row = parse_ncbi_name(name)
            else:
                row = _empty_row(name)
        else:  # pragma: no cover
            row = _empty_row(name)
        rows.append(row)

    if taxonomy_levels:
        for row in rows:
            for short, full in taxonomy_levels.items():
                if short in row and row[short] and full not in row:
                    row[full] = row[short]
    return rows


def extract_taxonomy_from_table(
    tree_text: str, taxonomy_text: str, id_column: str = "id"
) -> pd.DataFrame:
    """加载分类表，补齐树中遗漏的末端（缺失行留空）。"""
    df = load_taxonomy_table(taxonomy_text, id_column=id_column)
    tree = parse_tree(tree_text)
    present = set(df[id_column].astype(str))
    missing = [t for t in (n.taxon.label for n in tree.leaf_node_iter()) if t and t not in present]
    if missing:
        extra = pd.DataFrame({id_column: missing})
        for col in df.columns:
            if col != id_column:
                extra[col] = ""
        df = pd.concat([df, extra], ignore_index=True)
    return df


def load_taxonomy_table(text: str, id_column: str = "id") -> pd.DataFrame:
    """加载分类表（CSV/TSV），校验 ID 列存在。"""
    df = parse_table_text(text)
    if id_column not in df.columns:
        raise TaxonomyError(f"分类表缺少 ID 列 {id_column!r}（现有列：{list(df.columns)[:10]}）")
    df[id_column] = df[id_column].astype(str).str.strip()
    return df


def taxonomy_table_to_records(df: pd.DataFrame, id_column: str = "id") -> list[dict[str, str]]:
    """DataFrame → 记录列表（保持列序，全部字符串化）。"""
    records: list[dict[str, str]] = []
    for _, row in df.iterrows():
        rec: dict[str, str] = {"name": str(row[id_column])}
        for col in df.columns:
            if col == id_column:
                continue
            val = row[col]
            rec[col] = "" if pd.isna(val) else str(val).strip()
        rec["source_format"] = "table"
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# 单系群判定
# ---------------------------------------------------------------------------


_RANK_FULL_NAMES: dict[str, str] = {
    "d": "Domain",
    "p": "Phylum",
    "c": "Class",
    "o": "Order",
    "f": "Family",
    "g": "Genus",
}


def _resolve_rank_column(df: pd.DataFrame, rank: str) -> str | None:
    """按等级解析分类列名：优先短名（``d/p/c/o/f/g/s``），次之全名（``Domain/…``）。

    返回 DataFrame 中的实际列名；等级不存在返回 ``None``。
    """
    short = RANK_COLUMNS.get(rank)
    if not short:
        return None
    if short in df.columns:
        return short
    full = _RANK_FULL_NAMES.get(short)
    if full is None:
        return None
    for cand in (full, full.lower()):
        if cand in df.columns:
            return cand
    return None


def _resolve_members(df: pd.DataFrame, id_column: str, rank: str, taxon: str) -> list[str]:
    """返回指定类群在分类表中的成员 ID 列表（含特殊标识符）。"""
    col = _resolve_rank_column(df, rank)
    if taxon in TREE_META_TAXA:
        if not col:
            return [str(v) for v in df[id_column]]
        d_col: str | None = None
        for cand in ("d", "Domain", "domain"):
            if cand in df.columns:
                d_col = cand
                break
        domain_vals = df[d_col] if d_col else pd.Series([""] * len(df), index=df.index)
        if taxon == "ROOT":
            return [str(v) for v in df[id_column]]
        target = {"LUCA": ("Bacteria", "Archaea"), "LACA": ("Archaea",), "LBCA": ("Bacteria",)}[
            taxon
        ]
        return [
            str(v)
            for v, d in zip(df[id_column], domain_vals, strict=True)
            if str(d).strip().lower() in {t.lower() for t in target}
        ]
    if col is None:
        raise TaxonomyError(f"不支持的等级：{rank}（可选 Domain/Phylum/Class/Order/Family/Genus）")
    values = df[col]
    return [str(v) for v, c in zip(df[id_column], values, strict=True) if str(c).strip() == taxon]


def _leaf_labels(node: dendropy.Node) -> set[str]:
    """节点子树内的全部末端标签。"""
    return {n.taxon.label for n in node.leaf_iter() if n.taxon and n.taxon.label}


def _is_clade_minus_subtrees(mrca: dendropy.Node, member_set: set[str]) -> bool:
    """并系判定：成员集是否为「某节点叶集减去若干完整子子树」的表达。

    类群 G 为并系 ⇔ 存在节点 N 使 G = clade(N) \\ (N 的若干完整子子树)。
    候选 N 必为成员 MRCA 或其祖先；只需检查 N 的每个直接子子树
    要么全部是成员、要么完全不含成员（不允许“部分成员”的子子树）。
    """
    node: dendropy.Node | None = mrca
    while node is not None:
        if member_set <= _leaf_labels(node):
            ok = True
            for child in node.child_node_iter():
                labels = _leaf_labels(child)
                if labels and not (labels <= member_set or member_set.isdisjoint(labels)):
                    ok = False
                    break
            if ok:
                return True
        node = node.parent_node
    return False


def _monophyly_status(tree: dendropy.Tree, member_labels: list[str]) -> tuple[str, str | None, int]:
    """判定单系性，返回 ``(status, lca_label, n_tips_in_clade)``。

    三分类采用标准系统发育学语义（对 tip 成员集判定）：
    - mono：MRCA 叶集 == 成员集（成员恰好构成完整子树）；
    - para：成员集可表达为「某节点叶集减若干完整子子树」
      （MRCA 叶集 ⊋ 成员集，且多余末端整体挂于子树外侧，如“clade 内
      多出一个外群末端”的经典并系演示）；
    - poly：不存在上述表达，即成员分散于 MRCA 的不同主谱系中
      （MRCA 叶集 ⊋ 成员集，但多余末端位于成员谱系之间）。
    """
    present = [lab for lab in member_labels if tree.find_node_with_taxon_label(lab) is not None]
    if not present:
        return "absent", None, 0
    try:
        mrca = tree.mrca(taxon_labels=present)
    except Exception:
        mrca = None
    if mrca is None:
        return "absent", None, 0
    clade_labels = [n.taxon.label for n in mrca.leaf_iter() if n.taxon and n.taxon.label]
    member_set = set(present)
    clade_set = set(clade_labels)
    if clade_set == member_set:
        status = "mono"
    elif _is_clade_minus_subtrees(mrca, member_set):
        status = "para"
    else:
        status = "poly"
    lca_label = mrca.label if mrca.label else None
    return status, lca_label, len(clade_labels)


def check_monophyly(
    tree_text: str,
    taxonomy_text: str,
    rank: str,
    taxa: list[str] | None = None,
    id_column: str = "id",
    _member_limit: int | None = 50,
) -> list[dict[str, Any]]:
    """检查指定等级的单系性，返回每个类群的判定结果。

    ``_member_limit``：结果中 ``member_ids`` 的上限（None=不截断；模板生成等内部
    场景传入 None 获取完整成员列表，避免大组被截断导致模板缺行）。
    """
    tree = parse_tree(tree_text)
    df = load_taxonomy_table(taxonomy_text, id_column=id_column)

    col = _resolve_rank_column(df, rank)
    if col is None and not taxa:
        raise TaxonomyError(f"不支持的等级：{rank}（可选 Domain/Phylum/Class/Order/Family/Genus）")

    # 收集目标类群
    all_tips = {n.taxon.label for n in tree.leaf_node_iter() if n.taxon and n.taxon.label}
    groups: list[str]
    if taxa:
        groups = [str(t).strip() for t in taxa]
        groups = [g for g in groups if g]
    else:
        if col is None:
            raise TaxonomyError(
                f"不支持的等级：{rank}（可选 Domain/Phylum/Class/Order/Family/Genus）"
            )
        groups = sorted({str(v).strip() for v in df[col] if str(v).strip()})[:200]

    results: list[dict[str, Any]] = []
    for group in groups:
        members = _resolve_members(df, id_column, rank, group)
        present = [m for m in members if m in all_tips]
        absent_count = len(members) - len(present)
        status, lca_label, n_in_clade = _monophyly_status(tree, present)
        results.append(
            {
                "group": group,
                "rank": rank,
                "status": status,
                "lca_node": lca_label,
                "member_count": len(members),
                "n_tips_in_clade": n_in_clade,
                "member_ids": present[:_member_limit] if _member_limit else present,
                "missing_ids": absent_count,
            }
        )
    return results


def summarize_monophyly(results: list[dict[str, Any]]) -> dict[str, int]:
    """汇总三分类计数。"""
    summary = {"mono": 0, "para": 0, "poly": 0, "absent": 0}
    for r in results:
        status = r["status"]
        if status in summary:
            summary[status] += 1
    return summary


# ---------------------------------------------------------------------------
# 条件美化（check-and-style）
# ---------------------------------------------------------------------------


def _render_tree_colors(members: list[str], color: str, row_type: str = "branch") -> str:
    lines = ["TREE_COLORS", "SEPARATOR TAB", "DATA"]
    for m in members:
        lines.append(f"{m}\t{row_type}\t{color}\tnormal\t2")
    return "\n".join(lines) + "\n"


def check_and_style(
    tree_text: str,
    taxonomy_text: str,
    taxon: str,
    rank: str,
    action: str,
    color: str | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """单系群判定 → 条件美化。

    ``action``：``color_branch`` / ``highlight`` / ``color_strip`` / ``collapse``。
    ``strict=True`` 且非单系群 → 抛 ``TaxonomyError``；否则跳过并注明原因。
    """
    if action not in MONOPHYLY_ACTIONS:
        raise TaxonomyError(f"未知美化操作：{action}（可选 {'/'.join(MONOPHYLY_ACTIONS)}）")
    if not color:
        color = {
            "color_branch": "#FF0000",
            "highlight": "#FFD700",
            "color_strip": "#FF0000",
            "collapse": "#FF0000",
        }[action]
    from itol_mcp.utils.color_tools import validate_color

    color = validate_color(color)

    results = check_monophyly(tree_text, taxonomy_text, rank, taxa=[taxon], _member_limit=None)
    if not results:
        raise TaxonomyError(f"类群 {taxon} 在分类表中不存在")
    info = results[0]
    status = info["status"]
    if status == "absent":
        raise TaxonomyError(f"类群 {taxon} 在树中不存在任何成员（ID 不匹配或类群为空）")
    if status != "mono":
        reason = {"para": "并系（paraphyletic）", "poly": "复系（polyphyletic）"}.get(
            status, status
        )
        if strict:
            raise TaxonomyError(
                f"类群 {taxon} 为{reason}，strict=true 已拒绝执行美化，请先检查分类学分配"
            )
        return {
            "status": status,
            "action_applied": False,
            "group_info": {
                "group": taxon,
                "rank": rank,
                "member_count": info["member_count"],
                "member_ids": info["member_ids"],
                "lca_node": info["lca_node"],
                "n_tips_in_clade": info["n_tips_in_clade"],
                "missing_ids": info["missing_ids"],
            },
            "template": None,
            "skipped_reason": f"类群 {taxon} 为{reason}，已跳过美化（可设置 strict=true 强制报错）",
        }

    members = info["member_ids"]
    if action == "color_branch":
        template = _render_tree_colors(members, color, row_type="branch")
        header = "TREE_COLORS"
    elif action == "highlight":
        template = _render_tree_colors(members, color, row_type="label")
        header = "TREE_COLORS"
    elif action == "collapse":
        lines = ["COLLAPSE", "SEPARATOR TAB"]
        lines.extend(f"{m}\t1" for m in members)
        template = "\n".join(lines) + "\n"
        header = "COLLAPSE"
    else:  # color_strip
        lines = [
            "DATASET_COLORSTRIP",
            "SEPARATOR TAB",
            f"DATASET_LABEL {taxon}",
            f"COLOR {color}",
            "LEGEND_TITLE " + taxon,
            "LEGEND_POSITION 4",
            "DATA",
        ]
        for m in members:
            lines.append(f"{m}\t{taxon}\t{color}")
        template = "\n".join(lines) + "\n"
        header = "DATASET_COLORSTRIP"

    return {
        "status": status,
        "action_applied": True,
        "group_info": {
            "group": taxon,
            "rank": rank,
            "member_count": info["member_count"],
            "member_ids": info["member_ids"],
            "lca_node": info["lca_node"],
            "n_tips_in_clade": info["n_tips_in_clade"],
            "missing_ids": info["missing_ids"],
        },
        "template": template,
        "template_header": header,
        "n_template_rows": len(members),
        "color": color,
        "action": action,
    }


def build_color_strip_rows(
    tree_text: str,
    taxonomy_text: str,
    id_column: str,
    column: str,
    palette: str | None = None,
    explicit_colors: dict | None = None,
) -> tuple[list[dict], list[str]]:
    """分类学驱动着色：按分类列给每个末端分配颜色。

    返回 ``(data_rows, warnings)``，每行 ``{id, value, color}``（供 color_strip 等模板使用）。
    """
    from itol_mcp.utils.color_tools import build_category_color_map

    df = load_taxonomy_table(taxonomy_text, id_column=id_column)
    if column not in df.columns:
        raise TaxonomyError(f"分类表缺少列 {column!r}（现有列：{list(df.columns)[:12]}）")
    value_map: dict[str, str] = {}
    for _, row in df.iterrows():
        value_map[str(row[id_column])] = str(row[column]).strip()
    tree = parse_tree(tree_text)
    rows: list[dict] = []
    for node in tree.leaf_node_iter():
        if not (node.taxon and node.taxon.label):
            continue
        label = node.taxon.label
        value = value_map.get(label, "")
        rows.append({"id": label, "value": value})

    values = [r["value"] for r in rows if r["value"]]
    color_map, warnings = build_category_color_map(
        values, palette=palette, explicit=explicit_colors or {}
    )
    for row in rows:
        row["color"] = color_map.get(row["value"], "")
    return rows, warnings


def numeric_column_values(
    tree_text: str,
    taxonomy_text: str,
    id_column: str,
    column: str,
) -> list[tuple[str, float]]:
    """提取指定列的数值（用于 simple_bar/heatmap/gradient 等数值型模板）。

    返回 ``[(id, value)]``，非数值单元格按 0 处理并附带警告（由调用方生成）。
    """
    df = load_taxonomy_table(taxonomy_text, id_column=id_column)
    if column not in df.columns:
        raise TaxonomyError(f"分类表缺少列 {column!r}（现有列：{list(df.columns)[:12]}）")
    result: list[tuple[str, float]] = []
    for _, row in df.iterrows():
        val = str(row[column]).strip()
        try:
            num = float(val)
        except ValueError:
            num = 0.0
        result.append((str(row[id_column]), num))
    return result
