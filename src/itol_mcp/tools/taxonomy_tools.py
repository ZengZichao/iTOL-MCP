"""组 C：分类学工具（工具 6–8，见《04 §4.4》）。"""

from __future__ import annotations

import pandas as pd

from itol_mcp.exceptions import UsageError
from itol_mcp.services.taxonomy_service import (
    check_and_style,
    check_monophyly,
    extract_taxonomy_from_names,
    load_taxonomy_table,
    summarize_monophyly,
    taxonomy_table_to_records,
)
from itol_mcp.tools.common import (
    MCPServerLike,
    Runtime,
    execute,
    parse_json,
    resolve_table_text,
    resolve_tree_text,
    split_commas,
)
from itol_mcp.utils.result import ToolResult

_MONOPHYLY_CSV_COLUMNS = [
    "group",
    "rank",
    "status",
    "lca_node",
    "member_count",
    "n_tips_in_clade",
    "missing_ids",
]


def register(server: MCPServerLike, runtime: Runtime) -> None:
    """向 MCP 服务器注册分类学工具。"""

    @server.tool(
        name="itol_taxonomy_extract",
        description=(
            "从树末端名称自动提取分类学信息（GTDB 分号式 / 嵌入式 / NCBI 双名法 / auto 自动嗅探 / mixed 混合），"
            "或对已有分类表格做列结构规范化。"
            "两种来源互斥：tree/tree_file（名称提取）或 taxonomy/taxonomy_file（表格规范化）。"
            'taxonomy_levels 为自定义级别前缀映射 JSON，如 {"d":"Domain","p":"Phylum"}。'
            "output 可指定 CSV 输出路径（工作区内）。"
        ),
    )
    def itol_taxonomy_extract(
        tree: str | None = None,
        tree_file: str | None = None,
        taxonomy: str | None = None,
        taxonomy_file: str | None = None,
        format: str = "auto",
        taxonomy_levels: str | None = None,
        output: str | None = None,
    ) -> dict:
        """从树末端名称提取分类学信息或规范化分类表。"""
        return execute(
            runtime.logger,
            "itol_taxonomy_extract",
            lambda: _taxonomy_extract_impl(
                runtime, tree, tree_file, taxonomy, taxonomy_file, format, taxonomy_levels, output
            ),
        )

    @server.tool(
        name="itol_taxonomy_monophyly",
        description=(
            "基于树 + 分类表检查指定类群（或该等级全部类群）的单系性，输出三分类结果："
            "mono（单系）/ para（并系）/ poly（复系）/ absent（树中无成员）。"
            "rank 可选：Domain/Phylum/Class/Order/Family/Genus。"
            "taxa 为逗号分隔的类群名（缺省则检查该等级全部，限制前 200 个）。"
            "output 可指定结果 CSV 输出路径。"
        ),
    )
    def itol_taxonomy_monophyly(
        tree: str | None = None,
        tree_file: str | None = None,
        taxonomy: str | None = None,
        taxonomy_file: str | None = None,
        rank: str = "",
        taxa: str | None = None,
        output: str | None = None,
    ) -> dict:
        """检查指定等级/类群的单系性。"""
        return execute(
            runtime.logger,
            "itol_taxonomy_monophyly",
            lambda: _monophyly_impl(
                runtime, tree, tree_file, taxonomy, taxonomy_file, rank, taxa, output
            ),
        )

    @server.tool(
        name="itol_taxonomy_check_and_style",
        description=(
            "单系群判定 → 条件美化：类群为单系时生成指定风格的 iTOL 注释模板，"
            "action 可选 color_branch（分支着色）/ highlight（标签高亮）/ color_strip（色带）/ collapse（折叠）。"
            "taxon 支持特殊宏类群 LUCA / LACA / LBCA / ROOT。"
            "taxonomy/taxonomy_file 缺省时将自动从树末端名称提取。"
            "strict=true 时非单系类群将报错；false 时跳过并注明原因。"
            "output 可指定模板输出路径（工作区内）。"
        ),
    )
    def itol_taxonomy_check_and_style(
        tree: str | None = None,
        tree_file: str | None = None,
        taxonomy: str | None = None,
        taxonomy_file: str | None = None,
        taxon: str = "",
        rank: str = "",
        action: str = "color_branch",
        color: str = "#FF0000",
        strict: bool = False,
        output: str | None = None,
    ) -> dict:
        """单系群判定后按动作生成美化模板。"""
        return execute(
            runtime.logger,
            "itol_taxonomy_check_and_style",
            lambda: _check_and_style_impl(
                runtime,
                tree,
                tree_file,
                taxonomy,
                taxonomy_file,
                taxon,
                rank,
                action,
                color,
                strict,
                output,
            ),
        )


# ---------------------------------------------------------------------------
# 实现
# ---------------------------------------------------------------------------


def _taxonomy_extract_impl(
    runtime: Runtime,
    tree: str | None,
    tree_file: str | None,
    taxonomy: str | None,
    taxonomy_file: str | None,
    format: str,
    taxonomy_levels: str | None,
    output: str | None,
) -> ToolResult:
    tree_text = resolve_tree_text(runtime, tree=tree, tree_file=tree_file, required=False)
    tax_text = resolve_table_text(
        runtime, inline=taxonomy, table_file=taxonomy_file, required=False, group_name="分类表"
    )
    if not tree_text and not tax_text:
        raise UsageError(
            "itol_taxonomy_extract 需要提供来源：tree/tree_file（名称提取）或 taxonomy/taxonomy_file（表格规范化），二者互斥"
        )
    if tree_text and tax_text:
        raise UsageError("tree/tree_file 与 taxonomy/taxonomy_file 互斥，请只提供其一")

    levels = parse_json(taxonomy_levels, "taxonomy_levels")
    if levels is not None and not isinstance(levels, dict):
        raise UsageError('taxonomy_levels 需为 JSON 对象（如 {"d":"Domain"}）')

    if tree_text:
        rows = extract_taxonomy_from_names(tree_text, fmt=format, taxonomy_levels=levels)
        columns = ["name", "d", "p", "c", "o", "f", "g", "s", "source_format"]
        source_detected = _dominant_format(rows)
        df = pd.DataFrame(rows, columns=columns)
        preview = rows[:5]
    else:
        df = load_taxonomy_table(tax_text, id_column="id")  # type: ignore[arg-type]
        records = taxonomy_table_to_records(df, id_column="id")
        rows = records
        columns = list(df.columns)
        source_detected = "table"
        preview = records[:5]

    output_file = None
    if output:
        csv_text = df.to_csv(index=False)
        existed = runtime.workspace.resolve(output).exists()
        runtime.workspace.write_text(output, csv_text, force=True)
        output_file = str(runtime.workspace.resolve(output))
        warnings = [f"输出文件已存在，已覆盖：{output_file}"] if existed else []
    else:
        warnings = []

    data = {
        "n_rows": len(rows),
        "columns": columns,
        "source_format_detected": source_detected,
        "preview": preview,
        "output_file": output_file,
    }
    return ToolResult.ok(
        f"分类学信息提取完成：{len(rows)} 行，格式 {source_detected}"
        + ("，已写入 " + output_file if output_file else ""),
        data,
        warnings=warnings,
    )


def _dominant_format(rows: list[dict]) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        fmt = str(row.get("source_format") or "unknown")
        counts[fmt] = counts.get(fmt, 0) + 1
    return max(counts, key=lambda k: counts[k]) if counts else "unknown"


def _monophyly_impl(
    runtime: Runtime,
    tree: str | None,
    tree_file: str | None,
    taxonomy: str | None,
    taxonomy_file: str | None,
    rank: str,
    taxa: str | None,
    output: str | None,
) -> ToolResult:
    if not rank:
        raise UsageError("参数 rank 必填（可选 Domain/Phylum/Class/Order/Family/Genus）")
    tree_text = resolve_tree_text(runtime, tree=tree, tree_file=tree_file)
    tax_text = resolve_table_text(
        runtime, inline=taxonomy, table_file=taxonomy_file, group_name="分类表"
    )
    taxa_list = split_commas(taxa) or None

    results = check_monophyly(tree_text, tax_text, rank=rank, taxa=taxa_list)  # type: ignore[arg-type]
    summary = summarize_monophyly(results)

    output_file = None
    if output:
        df = pd.DataFrame(
            [{k: r.get(k) for k in _MONOPHYLY_CSV_COLUMNS} for r in results],
            columns=_MONOPHYLY_CSV_COLUMNS,
        )
        existed = runtime.workspace.resolve(output).exists()
        runtime.workspace.write_text(output, df.to_csv(index=False), force=True)
        output_file = str(runtime.workspace.resolve(output))
        summary_rows = [f"已覆盖既有输出：{output_file}"] if existed else []

    data = {
        "n_checked": len(results),
        "results": results,
        "summary": summary,
        "output_file": output_file,
    }
    msg = (
        f"单系性检查完成：{summary['mono']} 单系 / {summary['para']} 并系 / "
        f"{summary['poly']} 复系 / {summary['absent']} 缺失（共 {len(results)} 个类群）"
    )
    return ToolResult.ok(msg, data, warnings=summary_rows if output else [])


def _check_and_style_impl(
    runtime: Runtime,
    tree: str | None,
    tree_file: str | None,
    taxonomy: str | None,
    taxonomy_file: str | None,
    taxon: str,
    rank: str,
    action: str,
    color: str,
    strict: bool,
    output: str | None,
) -> ToolResult:
    if not taxon:
        raise UsageError("参数 taxon 必填（支持普通类群名与 LUCA/LACA/LBCA/ROOT）")
    tree_text = resolve_tree_text(runtime, tree=tree, tree_file=tree_file)
    if not tree_text:
        raise UsageError("需要提供树（tree 或 tree_file）")
    tax_text = resolve_table_text(
        runtime, inline=taxonomy, table_file=taxonomy_file, required=False, group_name="分类表"
    )
    if not tax_text:
        # 缺省分类表：从树末端名称自动提取（ID 列规范化为主键 id）
        rows = extract_taxonomy_from_names(tree_text, fmt="auto")
        df = pd.DataFrame(rows)
        if "name" in df.columns and "id" not in df.columns:
            df = df.rename(columns={"name": "id"})
        tax_text = df.to_csv(index=False)
        if not tax_text.strip():
            raise UsageError("无法从树末端名称自动提取分类学信息，请提供 taxonomy/taxonomy_file")

    result = check_and_style(
        tree_text, tax_text, taxon=taxon, rank=rank, action=action, color=color, strict=strict
    )

    output_file = None
    warnings = []
    if result.get("template") and output:
        existed = runtime.workspace.resolve(output).exists()
        runtime.workspace.write_text(output, result["template"], force=True)
        output_file = str(runtime.workspace.resolve(output))
        if existed:
            warnings.append(f"输出文件已存在，已覆盖：{output_file}")

    data = {
        "status": result["status"],
        "action_applied": result["action_applied"],
        "group_info": result["group_info"],
        "skipped_reason": result.get("skipped_reason"),
        "template": result.get("template"),
        "template_header": result.get("template_header"),
        "n_template_rows": result.get("n_template_rows", 0) if result.get("action_applied") else 0,
        "color": result.get("color"),
        "action": action,
        "output_file": output_file,
    }
    if result.get("action_applied"):
        msg = f"类群「{taxon}」为单系，已生成 {action} 美化模板"
        if output_file:
            msg += f"（已写入 {output_file}）"
    else:
        msg = str(result.get("skipped_reason") or f"类群「{taxon}」非单系，已跳过美化")
    return ToolResult.ok(msg, data, warnings=warnings)
