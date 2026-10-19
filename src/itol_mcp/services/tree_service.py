"""树服务：Newick/Nexus 检测、解析、统计、输入校验（实现设计第 5.4 节）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import dendropy

from itol_mcp.exceptions import TreeParseError, WorkspaceError
from itol_mcp.utils.io import detect_control_chars, parse_table_text

_TIP_PREVIEW_LIMIT = 30


@dataclass
class TreeSummary:
    """树统计信息。"""

    format: str
    n_tips: int
    n_internal: int
    n_nodes: int
    has_branch_lengths: bool
    has_support_values: bool
    rooted: bool | None
    tips: list[str]
    internal_labels: list[str]
    warnings: list[str]
    max_depth: float | None = None
    total_branch_length: float | None = None


def detect_format(text: str) -> str:
    """检测树格式：Newick / Nexus。空文本抛 ``TreeParseError``。"""
    stripped = text.lstrip("\ufeff \t\r\n")
    if not stripped:
        raise TreeParseError("树内容为空")
    first_line = stripped.splitlines()[0].strip().upper() if stripped.splitlines() else ""
    if "#NEXUS" in stripped.upper() or "BEGIN TREES" in stripped.upper():
        return "nexus"
    if first_line.startswith("(") or ";" in stripped[:200]:
        return "newick"
    raise TreeParseError("无法识别树格式：需为 Newick（以 ( 开头）或 Nexus（含 #NEXUS）")


def parse_tree(text: str) -> dendropy.Tree:
    """解析树文本为 dendropy.Tree；失败抛 ``TreeParseError``（含疑似行号）。"""
    fmt = detect_format(text)
    try:
        return dendropy.Tree.get_from_string(text, schema=fmt)
    except Exception as exc:  # dendropy 抛任意解析异常
        line_no = _suspect_line(text, exc)
        raise TreeParseError(
            f"树解析失败（{fmt} 格式）：{exc}"
            + (f"；疑似问题位于第 {line_no} 行" if line_no else "")
        ) from exc


def _suspect_line(text: str, exc: Exception) -> int | None:
    """从解析异常文本中尽力提取行号。"""
    m = re.search(r"line\s*(\d+)", str(exc), re.IGNORECASE)
    if m:
        return int(m.group(1))
    # 回退：定位第一个括号不平衡的位置
    depth = 0
    for idx, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return text.count("\n", 0, idx) + 1
    return None


def summarize(text: str) -> TreeSummary:
    """解析并统计树。``text`` 为树内容（Newick/Nexus）。"""
    tree = parse_tree(text)
    fmt = detect_format(text)

    tips = [node.taxon.label for node in tree.leaf_node_iter()]
    n_tips = len(tips)
    n_internal = sum(1 for _ in tree.internal_nodes())
    n_nodes = sum(1 for _ in tree.nodes())
    warnings: list[str] = []

    # 分支长度
    lengths: list[float] = []
    for edge in tree.edges():
        if edge.length is not None:
            try:
                lengths.append(float(edge.length))
            except (TypeError, ValueError):
                pass
    has_branch_lengths = len(lengths) > 0
    total_branch_length = round(sum(lengths), 6) if lengths else None

    # 内部节点标注（support value）
    internal_labels = [n.label for n in tree.internal_nodes() if n.label is not None]
    # 排除 Newick 中常见的中性标注（如空串或仅空格）
    internal_labels = [lab for lab in internal_labels if str(lab).strip()]
    has_support_values = len(internal_labels) > 0

    # 根性：dendropy 按输入推断；Newick 无法可靠判定
    rooted: bool | None = None
    try:
        rooted = bool(tree.is_rooted)
    except Exception:
        rooted = None

    # 深度
    max_depth: float | None = None
    try:
        max_depth = max((dist for dist in tree.max_distance_from_root().values()), default=None)
        max_depth = round(float(max_depth), 6) if max_depth is not None else None
    except Exception:
        pass

    # 警告
    if not has_branch_lengths:
        warnings.append("树不包含分支长度（图中分支将等长显示）")
    tip_labels = [t for t in tips if t is not None]
    if len(set(tip_labels)) != len(tip_labels):
        warnings.append(f"存在重复的末端名称（{len(tip_labels) - len(set(tip_labels))} 个重复）")
    if len(tip_labels) < len(tips):
        warnings.append("存在未命名的末端节点")

    return TreeSummary(
        format=fmt,
        n_tips=n_tips,
        n_internal=n_internal,
        n_nodes=n_nodes,
        has_branch_lengths=has_branch_lengths,
        has_support_values=has_support_values,
        rooted=rooted,
        tips=tip_labels[:_TIP_PREVIEW_LIMIT],
        internal_labels=internal_labels[:_TIP_PREVIEW_LIMIT],
        warnings=warnings,
        max_depth=max_depth,
        total_branch_length=total_branch_length,
    )


def summarize_file_or_text(value: str, source: str = "text") -> TreeSummary:
    """拒绝超长内联文本；source=file 时交由调用方（Workspace）读取。

    本函数仅为兼容签名保留：内联文本直接处理，文件读取由工具层完成。
    """
    if source == "file":
        raise WorkspaceError("文件读取应由工作区服务完成，请传入树内容文本")
    return summarize(value)


# ---------------------------------------------------------------------------
# 输入校验（实现设计第 5.4 节：PASS / WARN / CRITICAL 矩阵）
# ---------------------------------------------------------------------------


def validate_tree_text(tree_text: str) -> list[dict[str, str]]:
    """树内容校验，返回 ``[{level, message}]``。"""
    checks: list[dict[str, str]] = []

    if not tree_text.strip():
        return [{"level": "CRITICAL", "message": "树内容为空"}]
    control = detect_control_chars(tree_text)
    for c in control:
        checks.append({"level": "CRITICAL", "message": f"树文本含{c}（潜在注入风险）"})

    # 括号平衡
    stripped_comments = _strip_newick_comments(tree_text)
    balance = 0
    for ch in stripped_comments:
        if ch == "(":
            balance += 1
        elif ch == ")":
            balance -= 1
    if balance != 0:
        checks.append({"level": "CRITICAL", "message": f"括号不平衡（净差 {balance}），树结构非法"})

    # 多根：多个以 ; 结尾的语句
    if stripped_comments.count(";") > 1:
        checks.append(
            {"level": "CRITICAL", "message": "检测到多个根节点（多棵树拼接），iTOL 仅接受单根树"}
        )

    # 负分支长度
    neg = re.findall(r":\s*(-[\d.]+(?:[eE][+-]?\d+)?)", stripped_comments)
    if neg:
        checks.append(
            {"level": "CRITICAL", "message": f"存在负分支长度（{neg[:3]}…），iTOL 无法渲染"}
        )

    # 尝试解析以获得更细的结构校验
    try:
        tree = parse_tree(tree_text)
    except Exception as exc:
        checks.append({"level": "CRITICAL", "message": f"解析失败：{exc}"})
        return checks

    tips = [n.taxon.label for n in tree.leaf_node_iter()]
    unnamed = [t for t in tips if t is None or not str(t).strip()]
    if unnamed:
        checks.append(
            {
                "level": "ERROR",
                "message": f"存在 {len(unnamed)} 个空末端名称（模板数据集将无法匹配）",
            }
        )
    dup = len(tips) - len(set(tips))
    if dup:
        checks.append({"level": "ERROR", "message": f"存在 {dup} 个重复末端名称"})

    if not checks:
        checks.append({"level": "PASS", "message": "树结构校验通过"})
    return checks


def _strip_newick_comments(text: str) -> str:
    """去除 Newick 注释 ``[ ... ]`` 段。"""
    result = []
    depth = 0
    for ch in text:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth = max(0, depth - 1)
        elif depth == 0:
            result.append(ch)
    return "".join(result)


def validate_taxonomy_text(taxonomy_text: str, id_column: str = "id") -> list[dict[str, str]]:
    """分类表校验，返回 ``[{level, message}]``。"""
    checks: list[dict[str, str]] = []
    try:
        df = parse_table_text(taxonomy_text)
    except Exception as exc:
        return [{"level": "CRITICAL", "message": f"分类表解析失败：{exc}"}]
    if id_column not in df.columns:
        existing = [
            c for c in df.columns if str(c).strip().lower() in ("id", "name", "taxon", "tip")
        ]
        if existing:
            checks.append(
                {"level": "WARN", "message": f"未找到 ID 列 {id_column!r}，可用列：{existing[:5]}…"}
            )
        else:
            checks.append(
                {
                    "level": "CRITICAL",
                    "message": f"分类表缺少 ID 列 {id_column!r}（现有列：{list(df.columns)[:8]}）",
                }
            )
            return checks
        id_col = existing[0]
    else:
        id_col = id_column
    ids = df[id_col].astype(str).str.strip()
    empty = int(((ids == "") | ids.isna()).sum())
    if empty:
        checks.append({"level": "ERROR", "message": f"分类表存在 {empty} 个空 ID"})
    dup = int(ids.duplicated().sum())
    if dup:
        checks.append({"level": "WARN", "message": f"分类表存在 {dup} 个重复 ID"})
    if not checks:
        checks.append({"level": "PASS", "message": f"分类表校验通过（{len(df)} 行）"})
    return checks


_SEQ_ALPHABETS: dict[str, tuple[str, ...]] = {
    "dna": ("A", "C", "G", "T", "N", "R", "Y", "S", "W", "K", "M", "B", "D", "H", "V"),
    "rna": ("A", "C", "G", "U", "N", "R", "Y", "S", "W", "K", "M", "B", "D", "H", "V"),
    "protein": tuple("ACDEFGHIKLMNPQRSTVWY" + "X*BZJUO"),
}


def validate_sequence_text(sequence_text: str, alphabet: str = "auto") -> list[dict[str, str]]:
    """FASTA 序列校验（DNA/RNA/protein 或 auto 嗅探），返回 ``[{level, message}]``。"""
    checks: list[dict[str, str]] = []
    if not sequence_text.strip():
        return [{"level": "CRITICAL", "message": "序列内容为空"}]
    records = _parse_fasta(sequence_text)
    if not records:
        return [{"level": "CRITICAL", "message": "序列文件不是有效 FASTA（未找到 > 起始的记录）"}]

    alphabet = (alphabet or "auto").lower()
    if alphabet not in ("dna", "rna", "protein", "auto"):
        return [
            {"level": "CRITICAL", "message": f"未知字母表：{alphabet}（可选 dna/rna/protein/auto）"}
        ]

    lengths = {rec[0]: len(rec[1]) for rec in records}
    if len(set(lengths.values())) > 1:
        checks.append(
            {"level": "WARN", "message": "序列长度不一致（比对文件可能未对齐，或属非比对数据）"}
        )

    if alphabet == "auto":
        sample = "".join(rec[1] for rec in records)[:2000].upper()
        if not sample:
            alphabet_s = "protein"
        else:
            dna_chars = sum(1 for c in sample if c in "ACGTN")
            rna_chars = sum(1 for c in sample if c in "U")
            if len(sample) and (
                dna_chars / len(sample) > 0.9 or (dna_chars + rna_chars) / len(sample) > 0.95
            ):
                alphabet_s = "rna" if rna_chars > dna_chars * 0.1 else "dna"
            else:
                alphabet_s = "protein"
    else:
        alphabet_s = alphabet

    allowed = set(_SEQ_ALPHABETS.get(alphabet_s, ()))
    for name, seq in records:
        bad = {c.upper() for c in seq if c.upper() not in allowed and not c.isspace()}
        if bad:
            checks.append(
                {
                    "level": "WARN",
                    "message": f"序列 {name!r} 含非{['DNA', 'RNA', 'protein'][['dna', 'rna', 'protein'].index(alphabet_s)]}字符：{sorted(bad)[:8]}",
                }
            )
    if not checks:
        checks.append(
            {"level": "PASS", "message": f"序列校验通过（{len(records)} 条，字母表 {alphabet_s}）"}
        )
    return checks


def _parse_fasta(text: str) -> list[tuple[str, str]]:
    """极简 FASTA 解析：返回 ``[(header, seq)]``。"""
    records: list[tuple[str, str]] = []
    name = ""
    seq_parts: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith(">"):
            if name:
                records.append((name, "".join(seq_parts)))
            name = line[1:].split()[0]
            seq_parts = []
        elif name:
            seq_parts.append(line)
    if name:
        records.append((name, "".join(seq_parts)))
    return records


def validate_batch(
    tree_text: str | None = None,
    taxonomy_text: str | None = None,
    sequence_text: str | None = None,
    alphabet: str = "auto",
    id_column: str = "id",
) -> dict[str, Any]:
    """批量校验树/分类表/序列，返回 ``{"checks": {...}, "all_passed": bool}``。"""
    result: dict[str, list[dict[str, str]]] = {}
    if tree_text is not None:
        result["tree"] = validate_tree_text(tree_text)
    if taxonomy_text is not None:
        result["taxonomy"] = validate_taxonomy_text(taxonomy_text, id_column=id_column)
    if sequence_text is not None:
        result["sequence"] = validate_sequence_text(sequence_text, alphabet=alphabet)

    all_passed = all(
        check["level"] in ("PASS", "WARN") for group in result.values() for check in group
    )
    return {"checks": result, "all_passed": all_passed, "alphabet_detected": alphabet}
