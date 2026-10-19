"""组 B：树分析工具（工具 4–5，见《04 §4.3》）。"""

from __future__ import annotations

from itol_mcp.services.tree_service import summarize, validate_batch
from itol_mcp.tools.common import (
    MCPServerLike,
    Runtime,
    execute,
    resolve_table_text,
    resolve_tree_text,
)
from itol_mcp.utils.result import ToolResult


def register(server: MCPServerLike, runtime: Runtime) -> None:
    """向 MCP 服务器注册树分析工具。"""

    @server.tool(
        name="itol_tree_info",
        description=(
            "解析系统发育树（Newick/Nexus）并返回统计信息：格式、末端/内部节点数、是否有分支长度、"
            "是否有支持值、根性、最大深度、总分支长度与末端预览。"
            "tree 与 tree_file 二选一（内联文本 或 工作区内文件路径，如 data/tree.nwk）；解析失败将给出疑似行号。"
        ),
    )
    def itol_tree_info(tree: str | None = None, tree_file: str | None = None) -> dict:
        """解析树并返回统计信息。"""
        return execute(
            runtime.logger,
            "itol_tree_info",
            lambda: _tree_info_impl(runtime, tree, tree_file),
        )

    @server.tool(
        name="itol_validate_inputs",
        description=(
            "批量校验树 / 分类表 / FASTA 序列（可只传部分），返回逐项校验矩阵："
            "每条检查含 level（PASS/WARN/ERROR/CRITICAL）与 message。"
            "校验规则：括号平衡、负分支长度、重复/空末端名、多根、控制字符、序列字母表、分类表 ID 列等。"
            "alphabet 可选 dna/rna/protein/auto（自动嗅探）；id_column 为分类表 ID 列名（默认 id）。"
        ),
    )
    def itol_validate_inputs(
        tree: str | None = None,
        tree_file: str | None = None,
        taxonomy: str | None = None,
        taxonomy_file: str | None = None,
        sequence: str | None = None,
        sequence_file: str | None = None,
        alphabet: str = "auto",
        id_column: str = "id",
    ) -> dict:
        """批量校验树/分类表/序列输入。"""
        return execute(
            runtime.logger,
            "itol_validate_inputs",
            lambda: _validate_inputs_impl(
                runtime,
                tree,
                tree_file,
                taxonomy,
                taxonomy_file,
                sequence,
                sequence_file,
                alphabet,
                id_column,
            ),
        )


# ---------------------------------------------------------------------------
# 实现
# ---------------------------------------------------------------------------


def _tree_info_impl(runtime: Runtime, tree: str | None, tree_file: str | None) -> ToolResult:
    text = resolve_tree_text(runtime, tree=tree, tree_file=tree_file)
    summary = summarize(text)  # type: ignore[arg-type]  # 已保证非 None
    data = {
        "format": summary.format,
        "n_tips": summary.n_tips,
        "n_internal": summary.n_internal,
        "n_nodes": summary.n_nodes,
        "has_branch_lengths": summary.has_branch_lengths,
        "has_support_values": summary.has_support_values,
        "rooted": summary.rooted,
        "max_depth": summary.max_depth,
        "total_branch_length": summary.total_branch_length,
        "tip_preview": summary.tips,
        "internal_labels_preview": summary.internal_labels,
        "warnings": summary.warnings,
    }
    return ToolResult.ok(
        f"树解析成功：{summary.format} 格式，{summary.n_tips} 个末端，{summary.n_nodes} 个节点",
        data,
        warnings=summary.warnings,
    )


def _validate_inputs_impl(
    runtime: Runtime,
    tree: str | None,
    tree_file: str | None,
    taxonomy: str | None,
    taxonomy_file: str | None,
    sequence: str | None,
    sequence_file: str | None,
    alphabet: str,
    id_column: str,
) -> ToolResult:
    tree_text = resolve_tree_text(runtime, tree=tree, tree_file=tree_file, required=False)
    tax_text = resolve_table_text(
        runtime, inline=taxonomy, table_file=taxonomy_file, required=False, group_name="分类表"
    )
    seq_text = resolve_table_text(
        runtime, inline=sequence, table_file=sequence_file, required=False, group_name="序列文件"
    )
    if tree_text is None and tax_text is None and seq_text is None:
        from itol_mcp.exceptions import UsageError

        raise UsageError(
            "itol_validate_inputs 至少需要提供一类输入：tree/tree_file、taxonomy/taxonomy_file、sequence/sequence_file"
        )

    result = validate_batch(
        tree_text=tree_text,
        taxonomy_text=tax_text,
        sequence_text=seq_text,
        alphabet=alphabet,
        id_column=id_column,
    )
    all_passed = result["all_passed"]
    msg = "全部校验通过" if all_passed else "存在需关注的问题（WARN/ERROR/CRITICAL），详见 checks"
    return ToolResult.ok(msg, result, warnings=_flatten_warnings(result["checks"]))


def _flatten_warnings(checks: dict) -> list[str]:
    warnings: list[str] = []
    for group, items in checks.items():
        for item in items:
            if item["level"] in ("WARN", "ERROR", "CRITICAL"):
                warnings.append(f"[{group}] {item['level']}: {item['message']}")
    return warnings[:20]
