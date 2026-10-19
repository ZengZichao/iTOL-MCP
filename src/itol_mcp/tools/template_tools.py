"""组 D：模板生成工具（工具 9–24，见《04 §4.5》）。

- 工具 9：``itol_template_types``（注册表实时查询）
- 工具 10：``itol_template_create``（统一入口，支持数据三来源）
- 工具 11–22：12 个快捷入口（参数预绑定形态）
- 工具 23：``itol_template_bundle``（批量生成）
- 工具 24：``itol_template_validate``（规范校验）
"""

from __future__ import annotations

from typing import Any

from itol_mcp.exceptions import UsageError
from itol_mcp.services.template_service import (
    TemplateSpec,
    create_template,
    create_templates_bundle,
    get_template_type,
    list_template_types,
    validate_template,
)
from itol_mcp.services.tree_service import parse_tree
from itol_mcp.tools.common import (
    MCPServerLike,
    Runtime,
    execute,
    parse_json,
    resolve_table_text,
    resolve_tree_text,
    split_commas,
    table_to_rows,
)
from itol_mcp.utils.color_tools import build_category_color_map, validate_color
from itol_mcp.utils.io import format_number
from itol_mcp.utils.result import ToolResult

# 符号形状 → iTOL SYMBOL 类型码（见《附录A A.2》）
_SYMBOL_CODES = {
    "square": "1",
    "circle": "2",
    "star": "3",
    "triangle": "4",
    "right-triangle": "4",
    "left-triangle": "5",
}

# 连接线线型 → iTOL 数值（1=solid，2=straight）
_LINE_TYPES = {"solid": "1", "straight": "2"}


def register(server: MCPServerLike, runtime: Runtime) -> None:
    """向 MCP 服务器注册模板工具。"""

    # -- 工具 9 ---------------------------------------------------------

    @server.tool(
        name="itol_template_types",
        description=(
            "列出全部受支持的 iTOL 模板类型：类型名、头部（DATASET_*）、必需列、别名、可用参数白名单。"
            "template_type 指定时返回该类型详情；缺省返回全部。"
            "等价于资源 itol://help/template-types 的机器可读版（适合程序化解析）。"
        ),
    )
    def itol_template_types(template_type: str | None = None) -> dict:
        """列出模板类型注册表。"""
        return execute(
            runtime.logger,
            "itol_template_types",
            lambda: _template_types_impl(template_type),
        )

    # -- 工具 10 --------------------------------------------------------

    @server.tool(
        name="itol_template_create",
        description=(
            "按指定模板类型生成 iTOL 注释模板（统一入口，全部 32 种类型均可用）。"
            "数据来源三选一（互斥）：(a) data_rows 内联 JSON 行；(b) table_file 工作区表格 CSV/TSV；"
            "(c) tree_file(+tree) + taxonomy/taxonomy_file + column 分类学驱动着色（color_strip/heatmap/simple_bar/binary/gradient 等）。"
            "palette 可选 tol_bright/tol_vibrant/wong/okabeito/ibm；colors 为自定义色值映射 JSON。"
            "parameters 为类型专属参数（键名见 itol_template_types，如 WIDTH、STRIP_WIDTH、GRADIENT、FIELD_LABELS）。"
            "默认输出到 templates/<type>_<n>.txt。"
        ),
    )
    def itol_template_create(
        template_type: str = "",
        data_rows: list[dict] | None = None,
        table_file: str | None = None,
        tree: str | None = None,
        tree_file: str | None = None,
        taxonomy: str | None = None,
        taxonomy_file: str | None = None,
        column: str | None = None,
        label: str | None = None,
        color: str = "#ff0000",
        separator: str = "TAB",
        palette: str | None = None,
        colors: str | None = None,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
        id_column: str = "id",
    ) -> dict:
        """统一模板生成入口。"""
        return execute(
            runtime.logger,
            "itol_template_create",
            lambda: _template_create_impl(
                runtime,
                template_type,
                data_rows,
                table_file,
                tree,
                tree_file,
                taxonomy,
                taxonomy_file,
                column,
                label,
                color,
                separator,
                palette,
                colors,
                parameters,
                output,
                force,
                id_column,
            ),
        )

    # -- 工具 11 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_color_strip",
        description=(
            "快捷生成色带模板（DATASET_COLORSTRIP）：将分类列或 data_rows 映射为末端色带。"
            "数据来源：tree_file+taxonomy_file+column（分类学驱动自动配色）或 data_rows=[{id,value}]（可选 colors 显式映射）。"
            "palette 选择配色方案；strip_width 为色带像素宽度。"
        ),
    )
    def itol_template_create_color_strip(
        tree_file: str | None = None,
        tree: str | None = None,
        taxonomy_file: str | None = None,
        taxonomy: str | None = None,
        column: str | None = None,
        data_rows: list[dict] | None = None,
        label: str = "color_strip",
        colors: str | None = None,
        palette: str | None = None,
        strip_width: int = 50,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
        id_column: str = "id",
    ) -> dict:
        """生成色带模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_color_strip",
            lambda: _color_strip_impl(
                runtime,
                tree_file,
                tree,
                taxonomy_file,
                taxonomy,
                column,
                data_rows,
                label,
                colors,
                palette,
                strip_width,
                parameters,
                output,
                force,
                id_column,
            ),
        )

    # -- 工具 12 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_heatmap",
        description=(
            "快捷生成热图模板（DATASET_HEATMAP）：多列数值数据。"
            "数据来源 data_rows=[{id, col1, col2,...}] 或 table_file；columns 为逗号分隔的数值列名（必填）。"
            "gradient 为逗号分隔 2–5 个色值定义渐变（如 '#ff0000,#0000ff,#ffff00'）。"
        ),
    )
    def itol_template_create_heatmap(
        data_rows: list[dict] | None = None,
        table_file: str | None = None,
        columns: str = "",
        gradient: str | None = None,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成热图模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_heatmap",
            lambda: _heatmap_impl(
                runtime, data_rows, table_file, columns, gradient, parameters, output, force
            ),
        )

    # -- 工具 13 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_simple_bar",
        description=(
            "快捷生成单值柱状图模板（DATASET_SIMPLEBAR）。"
            "数据来源 data_rows=[{id, value}] 或 table_file；column 为数值列名（必填）。"
            "bar_color 为柱色（默认 #3c5484），bar_width 为柱宽像素。"
        ),
    )
    def itol_template_create_simple_bar(
        data_rows: list[dict] | None = None,
        table_file: str | None = None,
        column: str = "",
        bar_color: str = "#3c5484",
        bar_width: int = 50,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成单值柱状图模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_simple_bar",
            lambda: _simple_bar_impl(
                runtime,
                data_rows,
                table_file,
                column,
                bar_color,
                bar_width,
                parameters,
                output,
                force,
            ),
        )

    # -- 工具 14 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_multi_bar",
        description=(
            "快捷生成多值柱状图模板（DATASET_MULTIBAR）。"
            "columns 为逗号分隔的多列数值（必填）；field_labels 为字段标签；"
            "colors 为每字段颜色 JSON 数组；width 为总宽；alignment 可选 center/left/right。"
        ),
    )
    def itol_template_create_multi_bar(
        data_rows: list[dict] | None = None,
        table_file: str | None = None,
        columns: str = "",
        field_labels: str | None = None,
        colors: str | None = None,
        width: int = 1000,
        alignment: str = "center",
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成多值柱状图模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_multi_bar",
            lambda: _multi_bar_impl(
                runtime,
                data_rows,
                table_file,
                columns,
                field_labels,
                colors,
                width,
                alignment,
                parameters,
                output,
                force,
            ),
        )

    # -- 工具 15 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_binary",
        description=(
            "快捷生成二元矩阵模板（DATASET_BINARY）：0/1 存在-缺失矩阵。"
            'columns 为逗号分隔的 0/1 列（必填）；colors 为两色 JSON 数组，如 ["#ffffff","#000000"]。'
        ),
    )
    def itol_template_create_binary(
        data_rows: list[dict] | None = None,
        table_file: str | None = None,
        columns: str = "",
        colors: str | None = None,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成二元矩阵模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_binary",
            lambda: _binary_impl(
                runtime, data_rows, table_file, columns, colors, parameters, output, force
            ),
        )

    # -- 工具 16 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_gradient",
        description=(
            "快捷生成数值渐变色带模板（DATASET_GRADIENT）。"
            "column 为数值列（必填）；color_min/color_max 定义渐变两端色，use_mid_color 启用中间色 color_mid；"
            "strip_width 为色带宽度像素。value 将自动归一化到 0–1。"
        ),
    )
    def itol_template_create_gradient(
        data_rows: list[dict] | None = None,
        table_file: str | None = None,
        column: str = "",
        color_min: str = "#ff0000",
        color_max: str = "#0000ff",
        use_mid_color: bool = False,
        color_mid: str = "#ffff00",
        strip_width: int = 25,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成数值渐变色带模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_gradient",
            lambda: _gradient_impl(
                runtime,
                data_rows,
                table_file,
                column,
                color_min,
                color_max,
                use_mid_color,
                color_mid,
                strip_width,
                parameters,
                output,
                force,
            ),
        )

    # -- 工具 17 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_symbols",
        description=(
            "快捷生成符号标记模板（DATASET_SYMBOL）。"
            "column 为类别或数值列（必填）；symbol_type 可选 square/circle/triangle/star/left-triangle/right-triangle；"
            'colors 为类别→颜色 JSON 映射（如 {"A":"#aa0000"}）；size 为符号尺寸。'
        ),
    )
    def itol_template_create_symbols(
        data_rows: list[dict] | None = None,
        table_file: str | None = None,
        column: str = "",
        symbol_type: str = "circle",
        colors: str | None = None,
        size: int = 30,
        position: int = 0,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成符号标记模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_symbols",
            lambda: _symbols_impl(
                runtime,
                data_rows,
                table_file,
                column,
                symbol_type,
                colors,
                size,
                position,
                parameters,
                output,
                force,
            ),
        )

    # -- 工具 18 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_pie_chart",
        description=(
            "快捷生成饼图模板（DATASET_PIECHART）。"
            "columns 为逗号分隔的比例列（必填）；colors 为分片颜色 JSON 数组；pie_size 为饼直径像素。"
        ),
    )
    def itol_template_create_pie_chart(
        data_rows: list[dict] | None = None,
        table_file: str | None = None,
        columns: str = "",
        colors: str | None = None,
        pie_size: int = 50,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成饼图模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_pie_chart",
            lambda: _pie_chart_impl(
                runtime, data_rows, table_file, columns, colors, pie_size, parameters, output, force
            ),
        )

    # -- 工具 19 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_connections",
        description=(
            "快捷生成连接线模板（DATASET_CONNECTION）：连接两个末端（或末端↔内部节点）。"
            "connections 数据行：[{source1, source2, color?, width?, line_type?}]，line_type 可选 solid/straight。"
            "parameters 可传 CURVE、CURVATURE、CONNECTION_TYPE、LINE_WIDTH 等（见 itol_template_types）。"
        ),
    )
    def itol_template_create_connections(
        connections: list[dict] | None = None,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成连接线模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_connections",
            lambda: _connections_impl(runtime, connections, parameters, output, force),
        )

    # -- 工具 20 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_domains",
        description=(
            "快捷生成蛋白质/功能域架构模板（DATASET_DOMAINS）。"
            "data_rows：[{id, type, start, end, color?}]（同 id 多行=多域）。"
            "domain_colors 为域类型→颜色 JSON 映射；parameters 可传 STROKE_WIDTH、MARGIN、USE_MID_LINE 等。"
        ),
    )
    def itol_template_create_domains(
        data_rows: list[dict] | None = None,
        domain_colors: str | None = None,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成域架构模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_domains",
            lambda: _domains_impl(runtime, data_rows, domain_colors, parameters, output, force),
        )

    # -- 工具 21 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_boxplot",
        description=(
            "快捷生成箱线图模板（DATASET_BOXPLOT）：数据为预计算的 min/q1/median/q3/max 五数概括列。"
            "extremes 为极端值列名（逗号分隔，可选，将作为额外列输出）。color 为箱色；width 为总宽。"
        ),
    )
    def itol_template_create_boxplot(
        data_rows: list[dict] | None = None,
        table_file: str | None = None,
        min: str = "",
        q1: str = "",
        median: str = "",
        q3: str = "",
        max: str = "",
        extremes: str | None = None,
        color: str = "#00ff00",
        width: int = 1500,
        parameters: dict | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成箱线图模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_boxplot",
            lambda: _boxplot_impl(
                runtime,
                data_rows,
                table_file,
                min,
                q1,
                median,
                q3,
                max,
                extremes,
                color,
                width,
                parameters,
                output,
                force,
            ),
        )

    # -- 工具 22 --------------------------------------------------------

    @server.tool(
        name="itol_template_create_tree_ops",
        description=(
            "快捷生成树结构操作模板（四合一）：kind 可选 collapse（折叠）/ prune（修剪）/ spacing（间距）/ treestyle（树样式）。"
            "data_rows：collapse=[{id, collapse?}]、prune=[{id}]、spacing=[{id, space}]、treestyle=[{id, style, width?, color?}]。"
            "tree_file 可选提供，用于校验 ID 与树匹配（不匹配给出警告）。"
        ),
    )
    def itol_template_create_tree_ops(
        kind: str = "",
        data_rows: list[dict] | None = None,
        tree_file: str | None = None,
        tree: str | None = None,
        output: str | None = None,
        force: bool = False,
    ) -> dict:
        """生成树结构操作模板。"""
        return execute(
            runtime.logger,
            "itol_template_create_tree_ops",
            lambda: _tree_ops_impl(runtime, kind, data_rows, tree_file, tree, output, force),
        )

    # -- 工具 23 --------------------------------------------------------

    @server.tool(
        name="itol_template_bundle",
        description=(
            "一次生成多个 iTOL 模板（接收模板规格 JSON 数组，每个元素为 itol_template_create 的参数子集，必含 template_type），"
            "统一写入 templates/<bundle_name>/，便于一次上传多个数据集。"
            "可提供共享的 tree_file(+tree) 与 taxonomy/taxonomy_file 供多规格复用（规格内 data_rows/table_file 优先）。"
        ),
    )
    def itol_template_bundle(
        specs: list[dict] | None = None,
        bundle_name: str = "bundle",
        tree_file: str | None = None,
        tree: str | None = None,
        taxonomy_file: str | None = None,
        taxonomy: str | None = None,
    ) -> dict:
        """批量生成模板。"""
        return execute(
            runtime.logger,
            "itol_template_bundle",
            lambda: _bundle_impl(
                runtime, specs, bundle_name, tree_file, tree, taxonomy_file, taxonomy
            ),
        )

    # -- 工具 24 --------------------------------------------------------

    @server.tool(
        name="itol_template_validate",
        description=(
            "校验已生成的模板文本/文件是否符合 iTOL 注释文件规范：头部、分隔符、DATA 段、行内列数一致性、色值、"
            "以及（提供树时）数据行 ID 与树的匹配度。返回逐项 checks（PASS/WARN/CRITICAL）与匹配统计。"
        ),
    )
    def itol_template_validate(
        template: str | None = None,
        template_file: str | None = None,
        tree: str | None = None,
        tree_file: str | None = None,
    ) -> dict:
        """校验模板文本规范。"""
        return execute(
            runtime.logger,
            "itol_template_validate",
            lambda: _validate_impl(runtime, template, template_file, tree, tree_file),
        )


# ---------------------------------------------------------------------------
# 共享实现
# ---------------------------------------------------------------------------


def _finish(
    runtime: Runtime,
    spec: TemplateSpec,
    output: str | None,
    force: bool,
    message: str | None = None,
) -> ToolResult:
    """渲染 → 写入 → 生成 ToolResult（含 files[].text_preview）。"""
    created = create_template(spec, runtime.workspace, out_path=output, force=force)
    text = _read_created(runtime, created["file"])
    validation = validate_template(text)
    n_rows = validation["n_data_rows"]
    data = {
        "template_type": created["template_type"],
        "header": created["header"],
        "n_rows": n_rows,
        "label": created["label"],
        "output": created["file"],
    }
    files = [
        {
            "path": created["file"],
            "kind": "template",
            "bytes": len(text.encode("utf-8")),
            "text_preview": "\n".join(text.splitlines()[:40]),
        }
    ]
    msg = message or f"模板已生成：{created['header']}（{n_rows} 行数据）"
    return ToolResult.ok(msg, data, warnings=created["warnings"], files=files)


def _read_created(runtime: Runtime, rel_path: str) -> str:
    """读取 create_template 返回值中的文件内容。"""
    return (runtime.workspace.root / rel_path).resolve().read_text(encoding="utf-8")


def _rows_from_data(
    runtime: Runtime, data_rows: list[dict] | None, table_file: str | None
) -> list[dict]:
    """数据来源解析：data_rows（内联）或 table_file（工作区表格）。"""
    if data_rows:
        return [
            {str(k): v for k, v in r.items() if not (isinstance(r.get(k), str) and r[k] == "")}
            for r in data_rows
            if isinstance(r, dict)
        ]
    if table_file:
        text = runtime.workspace.read_text(table_file, max_bytes=runtime.config.max_file_bytes)
        return table_to_rows(text)
    return []


def _require_columns(rows: list[dict], required: list[str], label: str) -> None:
    """校验数据行包含必需列。"""
    if not rows:
        raise UsageError(f"{label}：未提供数据（data_rows 为空或 table_file 无有效数据行）")
    first_rows = rows[0]
    missing = [c for c in required if c not in first_rows]
    if missing:
        raise UsageError(f"{label}：数据缺少列 {missing}（现有列：{list(first_rows.keys())}）")


def _taxonomy_spec(
    spec: TemplateSpec,
    runtime: Runtime,
    tree: str | None,
    tree_file: str | None,
    taxonomy: str | None,
    taxonomy_file: str | None,
    column: str | None,
    palette: str | None,
    id_column: str,
) -> bool:
    """尝试构建分类学驱动规格；未启用返回 False。"""
    if not ((tree or tree_file) and (taxonomy or taxonomy_file) and column):
        return False
    spec.tree = resolve_tree_text(runtime, tree=tree, tree_file=tree_file)
    spec.taxonomy = resolve_table_text(
        runtime, inline=taxonomy, table_file=taxonomy_file, group_name="分类表"
    )
    spec.column = column
    spec.palette = palette
    spec.id_column = id_column or "id"
    return True


# ---------------------------------------------------------------------------
# 工具 9–10 实现
# ---------------------------------------------------------------------------


def _template_types_impl(template_type: str | None) -> ToolResult:
    types = list_template_types()
    if template_type:
        info = get_template_type(template_type)  # 未知类型抛 TemplateTypeError（含可用列表）
        types = [t for t in types if t["type_name"] == info.type_name]
    return ToolResult.ok(
        f"模板类型查询完成（{len(types)} 条）", {"types": types, "total": len(types)}
    )


def _template_create_impl(
    runtime: Runtime,
    template_type: str,
    data_rows: list[dict] | None,
    table_file: str | None,
    tree: str | None,
    tree_file: str | None,
    taxonomy: str | None,
    taxonomy_file: str | None,
    column: str | None,
    label: str | None,
    color: str,
    separator: str,
    palette: str | None,
    colors: str | None,
    parameters: dict | None,
    output: str | None,
    force: bool,
    id_column: str,
) -> ToolResult:
    if not template_type:
        raise UsageError("参数 template_type 必填（可用类型见 itol_template_types）")
    get_template_type(template_type)  # 提前校验类型

    spec = TemplateSpec(
        template_type=template_type,
        label=label or template_type,
        color=validate_color(color),
        separator=separator,
        parameters=dict(parameters or {}),
    )

    tax_driven = _taxonomy_spec(
        spec, runtime, tree, tree_file, taxonomy, taxonomy_file, column, palette, id_column
    )
    provided_sources = sum([bool(tax_driven), bool(data_rows), bool(table_file)])
    if provided_sources > 1:
        raise UsageError(
            "数据来源互斥：data_rows / table_file / (tree_file+taxonomy+column) 只能提供其一"
        )

    if not tax_driven:
        rows = _rows_from_data(runtime, data_rows, table_file)
        if not rows:
            raise UsageError(
                "至少提供一种数据来源：data_rows、table_file，或 tree_file(+tree)+taxonomy/taxonomy_file+column"
            )
        if colors:
            rows = _apply_explicit_colors(rows, colors, template_type)
        spec.data_rows = rows

    return _finish(runtime, spec, output, force)


def _apply_explicit_colors(rows: list[dict], colors: str, template_type: str) -> list[dict]:
    """按 colors 显式映射补全行颜色（color_strip/symbols 等）。"""
    parsed = parse_json(colors, "colors")
    if not isinstance(parsed, dict) or template_type not in ("color_strip", "symbols"):
        return rows
    out: list[dict] = []
    for row in rows:
        value = row.get("value", row.get("id", ""))
        out.append({**row, "color": str(parsed.get(str(value), "")) or row.get("color", "")})
    return out


# ---------------------------------------------------------------------------
# 工具 11–22 实现
# ---------------------------------------------------------------------------


def _color_strip_impl(
    runtime: Runtime,
    tree_file: str | None,
    tree: str | None,
    taxonomy_file: str | None,
    taxonomy: str | None,
    column: str | None,
    data_rows: list[dict] | None,
    label: str,
    colors: str | None,
    palette: str | None,
    strip_width: int,
    parameters: dict | None,
    output: str | None,
    force: bool,
    id_column: str,
) -> ToolResult:
    spec = TemplateSpec(
        template_type="color_strip",
        label=label or "color_strip",
        separator="TAB",
        parameters=dict(parameters or {}),
    )
    spec.parameters.setdefault("STRIP_WIDTH", strip_width)

    tax_driven = _taxonomy_spec(
        spec, runtime, tree, tree_file, taxonomy, taxonomy_file, column, palette, id_column
    )
    if not tax_driven:
        rows = _rows_from_data(runtime, data_rows, None)
        if not rows:
            raise UsageError(
                "color_strip 需要数据来源：tree_file+taxonomy_file+column，或 data_rows=[{id,value}]"
            )
        exclude = parse_json(colors, "colors") if colors else None
        spec.data_rows = _colorize_rows(
            rows, explicit=exclude if isinstance(exclude, dict) else None, palette=palette
        )

    return _finish(runtime, spec, output, force)


def _colorize_rows(rows: list[dict], explicit: dict | None, palette: str | None) -> list[dict]:
    """为色带行补全 value 与 color（缺省按 palette 或显式映射取色）。"""
    out: list[dict] = []
    for row in rows:
        rid = str(row.get("id") or row.get("value") or "")
        value = row.get("value")
        if value is None:
            value = row.get("color", rid)
        out.append({"id": rid, "value": str(value), "color": str(row.get("color") or "")})
    missing = [r for r in out if not r["color"]]
    if missing:
        mapping, _warnings = build_category_color_map(
            [r["value"] for r in out], palette=palette, explicit=explicit
        )
        for r in out:
            if not r["color"]:
                r["color"] = mapping.get(r["value"], "#999999")
    return out


def _heatmap_impl(
    runtime: Runtime,
    data_rows: list[dict] | None,
    table_file: str | None,
    columns: str,
    gradient: str | None,
    parameters: dict | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    cols = split_commas(columns)
    if not cols:
        raise UsageError("参数 columns 必填：逗号分隔的数值列名")
    rows = _rows_from_data(runtime, data_rows, table_file)
    _require_columns(rows, cols, "heatmap")
    spec = TemplateSpec(
        template_type="heatmap",
        label="heatmap",
        data_rows=[{"id": str(r.get("id", "")), **{c: r.get(c, "") for c in cols}} for r in rows],
        parameters=dict(parameters or {}),
    )
    if gradient:
        spec.parameters.setdefault("GRADIENT", gradient)
    return _finish(runtime, spec, output, force)


def _simple_bar_impl(
    runtime: Runtime,
    data_rows: list[dict] | None,
    table_file: str | None,
    column: str,
    bar_color: str,
    bar_width: int,
    parameters: dict | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    if not column:
        raise UsageError("参数 column 必填：数值列名")
    rows = _rows_from_data(runtime, data_rows, table_file)
    _require_columns(rows, [column], "simple_bar")
    spec = TemplateSpec(
        template_type="simple_bar",
        label="simple_bar",
        color=validate_color(bar_color),
        data_rows=[{"id": str(r.get("id", "")), "bar_height": r.get(column, "")} for r in rows],
        parameters=dict(parameters or {}),
    )
    spec.parameters.setdefault("BAR_WIDTH", bar_width)
    return _finish(runtime, spec, output, force)


def _multi_bar_impl(
    runtime: Runtime,
    data_rows: list[dict] | None,
    table_file: str | None,
    columns: str,
    field_labels: str | None,
    colors: str | None,
    width: int,
    alignment: str,
    parameters: dict | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    cols = split_commas(columns)
    if not cols:
        raise UsageError("参数 columns 必填：逗号分隔的多列数值")
    if alignment not in ("center", "left", "right"):
        raise UsageError("alignment 可选 center/left/right")
    rows = _rows_from_data(runtime, data_rows, table_file)
    _require_columns(rows, cols, "multi_bar")
    spec = TemplateSpec(
        template_type="multi_bar",
        label="multi_bar",
        data_rows=[{"id": str(r.get("id", "")), **{c: r.get(c, "") for c in cols}} for r in rows],
        parameters=dict(parameters or {}),
    )
    spec.parameters.setdefault("WIDTH", width)
    spec.parameters.setdefault("ALIGN_FIELDS", alignment)
    if field_labels:
        spec.parameters.setdefault("FIELD_LABELS", split_commas(field_labels))
    if colors:
        parsed = parse_json(colors, "colors")
        if isinstance(parsed, list):
            spec.parameters.setdefault("COLORS", ",".join(str(c) for c in parsed))
        elif isinstance(parsed, dict):
            spec.parameters.setdefault("COLORS", ",".join(parsed[k] for k in cols if k in parsed))
    return _finish(runtime, spec, output, force)


def _binary_impl(
    runtime: Runtime,
    data_rows: list[dict] | None,
    table_file: str | None,
    columns: str,
    colors: str | None,
    parameters: dict | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    cols = split_commas(columns)
    if not cols:
        raise UsageError("参数 columns 必填：逗号分隔的 0/1 列")
    rows = _rows_from_data(runtime, data_rows, table_file)
    _require_columns(rows, cols, "binary")
    spec = TemplateSpec(
        template_type="binary",
        label="binary",
        data_rows=[
            {"id": str(r.get("id", "")), **{c: _to_binary(r.get(c)) for c in cols}} for r in rows
        ],
        parameters=dict(parameters or {}),
    )
    if colors:
        parsed = parse_json(colors, "colors")
        if isinstance(parsed, list) and len(parsed) >= 2:
            spec.parameters.setdefault("COLORS", ",".join(str(c) for c in parsed[:2]))
    return _finish(runtime, spec, output, force)


def _to_binary(value: object) -> int:
    """任意值 → 0/1（'1'/'true'/正数 → 1）。"""
    if value is None:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value != 0 else 0
    return 1 if str(value).strip().lower() in ("1", "true", "yes", "y", "t") else 0


def _gradient_impl(
    runtime: Runtime,
    data_rows: list[dict] | None,
    table_file: str | None,
    column: str,
    color_min: str,
    color_max: str,
    use_mid_color: bool,
    color_mid: str,
    strip_width: int,
    parameters: dict | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    if not column:
        raise UsageError("参数 column 必填：数值列名")
    rows = _rows_from_data(runtime, data_rows, table_file)
    _require_columns(rows, [column], "gradient")
    spec = TemplateSpec(
        template_type="gradient",
        label="gradient",
        data_rows=[
            {"id": str(r.get("id", "")), "value": _normalize_value(r.get(column))} for r in rows
        ],
        parameters=dict(parameters or {}),
    )
    spec.parameters.setdefault("COLOR_MIN", validate_color(color_min))
    spec.parameters.setdefault("COLOR_MAX", validate_color(color_max))
    spec.parameters.setdefault("STRIP_WIDTH", strip_width)
    if use_mid_color:
        spec.parameters.setdefault("USE_MID_COLOR", "1")
        spec.parameters.setdefault("COLOR_MID", validate_color(color_mid))
    return _finish(runtime, spec, output, force)


def _normalize_value(value: Any) -> str:
    """数值归一化到 0–1（仅当能解析为数值时）。"""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return ""
    if num != num:  # NaN
        return ""
    return format_number(max(0.0, min(1.0, num / 100.0 if abs(num) > 1 else num)))


def _symbols_impl(
    runtime: Runtime,
    data_rows: list[dict] | None,
    table_file: str | None,
    column: str,
    symbol_type: str,
    colors: str | None,
    size: int,
    position: int,
    parameters: dict | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    if not column:
        raise UsageError("参数 column 必填：类别或数值列名")
    code = _SYMBOL_CODES.get(symbol_type)
    if code is None:
        raise UsageError(f"symbol_type 可选：{'/'.join(_SYMBOL_CODES)}")
    rows = _rows_from_data(runtime, data_rows, table_file)
    _require_columns(rows, [column], "symbols")
    explicit = parse_json(colors, "colors") if colors else None
    mapping = {}
    if isinstance(explicit, dict):
        mapping = explicit
    else:
        values = [str(r.get(column, "")) for r in rows]
        mapping, _warnings = build_category_color_map(values, palette=None)
    spec_rows: list[dict] = []
    for r in rows:
        raw = r.get(column, "")
        try:
            num = float(raw)
            value, color = format_number(num), validate_color("#999999")
        except (TypeError, ValueError):
            value, color = "1", str(mapping.get(str(raw), "#999999"))
        spec_rows.append({"id": str(r.get("id", "")), "type": code, "value": value, "color": color})
    spec = TemplateSpec(
        template_type="symbols",
        label="symbols",
        data_rows=spec_rows,
        parameters=dict(parameters or {}),
    )
    spec.parameters.setdefault("SIZE", size)
    spec.parameters.setdefault("POSITION", position)
    spec.parameters.setdefault("SHAPE", code)
    return _finish(runtime, spec, output, force)


def _pie_chart_impl(
    runtime: Runtime,
    data_rows: list[dict] | None,
    table_file: str | None,
    columns: str,
    colors: str | None,
    pie_size: int,
    parameters: dict | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    cols = split_commas(columns)
    if not cols:
        raise UsageError("参数 columns 必填：逗号分隔的比例列")
    rows = _rows_from_data(runtime, data_rows, table_file)
    _require_columns(rows, cols, "pie_chart")
    spec = TemplateSpec(
        template_type="pie_chart",
        label="pie_chart",
        data_rows=[{"id": str(r.get("id", "")), **{c: r.get(c, 0) for c in cols}} for r in rows],
        parameters=dict(parameters or {}),
    )
    spec.parameters.setdefault("SIZE", pie_size)
    if colors:
        parsed = parse_json(colors, "colors")
        if isinstance(parsed, list):
            spec.parameters.setdefault("COLORS", ",".join(str(c) for c in parsed))
    return _finish(runtime, spec, output, force)


def _connections_impl(
    runtime: Runtime,
    connections: list[dict] | None,
    parameters: dict | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    if not connections:
        raise UsageError("参数 connections 必填：[{source1, source2, color?, width?, line_type?}]")
    rows: list[dict] = []
    for c in connections:
        if not isinstance(c, dict):
            raise UsageError("connections 每个元素需为对象")
        row = {
            "source1": str(c.get("source1") or c.get("id1") or ""),
            "source2": str(c.get("source2") or c.get("id2") or ""),
        }
        if c.get("color"):
            row["color"] = validate_color(str(c["color"]))
        if c.get("width") is not None:
            row["width"] = format_number(c["width"])
        if c.get("line_type"):
            lt = str(c["line_type"]).strip().lower()
            row["line_type"] = _LINE_TYPES.get(lt, lt)
        rows.append(row)
    if any(not r["source1"] or not r["source2"] for r in rows):
        raise UsageError("connections 每行需要 source1 与 source2（末端或节点 ID）")
    spec = TemplateSpec(
        template_type="connections",
        label="connections",
        data_rows=rows,
        parameters=dict(parameters or {}),
    )
    return _finish(runtime, spec, output, force)


def _domains_impl(
    runtime: Runtime,
    data_rows: list[dict] | None,
    domain_colors: str | None,
    parameters: dict | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    if not data_rows:
        raise UsageError("参数 data_rows 必填：[{id, type, start, end, color?}]")
    cmap = parse_json(domain_colors, "domain_colors") if domain_colors else None
    if cmap is not None and not isinstance(cmap, dict):
        raise UsageError("domain_colors 需为 JSON 对象（域类型→颜色）")
    rows: list[dict] = []
    for r in data_rows:
        rid = str(r.get("id", ""))
        frm = r.get("from", r.get("start"))
        to = r.get("to", r.get("end"))
        typ = r.get("type", r.get("name", ""))
        if frm is None or to is None:
            raise UsageError(f"域行缺少 from/start 或 to/end：{r}")
        color = r.get("color") or (str(cmap.get(str(typ), "")) if cmap else "")
        rows.append(
            {
                "id": rid,
                "from": format_number(frm),
                "to": format_number(to),
                "type": str(typ) if not color else validate_color(color),
            }
        )
    spec = TemplateSpec(
        template_type="domains",
        label="domains",
        data_rows=rows,
        parameters=dict(parameters or {}),
    )
    return _finish(runtime, spec, output, force)


def _boxplot_impl(
    runtime: Runtime,
    data_rows: list[dict] | None,
    table_file: str | None,
    min: str,
    q1: str,
    median: str,
    q3: str,
    max: str,
    extremes: str | None,
    color: str,
    width: int,
    parameters: dict | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    for label, val in (("min", min), ("q1", q1), ("median", median), ("q3", q3), ("max", max)):
        if not val:
            raise UsageError(f"参数 {label} 必填：五数概括列名")
    rows = _rows_from_data(runtime, data_rows, table_file)
    _require_columns(rows, [min, q1, median, q3, max], "boxplot")
    extreme_cols = split_commas(extremes)
    for c in extreme_cols:
        _require_columns(rows, [c], "boxplot(extremes)")
    spec_rows: list[dict] = []
    for r in rows:
        row = {
            "id": str(r.get("id", "")),
            "minimum": r.get(min, ""),
            "q1": r.get(q1, ""),
            "median": r.get(median, ""),
            "q3": r.get(q3, ""),
            "maximum": r.get(max, ""),
        }
        for c in extreme_cols:
            row[c] = r.get(c, "")
        spec_rows.append(row)
    spec = TemplateSpec(
        template_type="boxplot",
        label="boxplot",
        color=validate_color(color),
        data_rows=spec_rows,
        parameters=dict(parameters or {}),
    )
    spec.parameters.setdefault("WIDTH", width)
    return _finish(runtime, spec, output, force)


_TREE_OPS_KINDS = ("collapse", "prune", "spacing", "treestyle")


def _tree_ops_impl(
    runtime: Runtime,
    kind: str,
    data_rows: list[dict] | None,
    tree_file: str | None,
    tree: str | None,
    output: str | None,
    force: bool,
) -> ToolResult:
    kind = (kind or "").strip().lower()
    if kind not in _TREE_OPS_KINDS:
        raise UsageError(f"kind 可选：{'/'.join(_TREE_OPS_KINDS)}")
    if not data_rows:
        raise UsageError(f"kind={kind} 需要 data_rows（见工具描述的行格式）")

    rows: list[dict] = []
    for r in data_rows:
        rid = str(r.get("id", ""))
        if not rid:
            raise UsageError("data_rows 每行需要 id")
        if kind == "collapse":
            rows.append({"id": rid, "value": r.get("collapse", r.get("value", "1"))})
        elif kind == "prune":
            rows.append({"id": rid})
        elif kind == "spacing":
            rows.append({"id": rid, "factor": r.get("space", r.get("factor", "1.0"))})
        else:  # treestyle
            style = r.get("style", "normal")
            row = {"id": rid, "type": r.get("type", "label"), "style": style}
            if r.get("width") is not None:
                row["width"] = format_number(r["width"])
            if r.get("color"):
                row["color"] = validate_color(str(r["color"]))
            rows.append(row)

    warnings: list[str] = []
    tree_text = resolve_tree_text(runtime, tree=tree, tree_file=tree_file, required=False)
    if tree_text:
        try:
            t = parse_tree(tree_text)
            known = {n.taxon.label for n in t.leaf_node_iter() if n.taxon and n.taxon.label}
            known |= {n.label for n in t.internal_nodes() if n.label}
            unmatched = [str(r.get("id")) for r in rows if str(r.get("id")) not in known]
            if unmatched:
                warnings.append(
                    f"以下 ID 与树不匹配：{unmatched[:10]}{'…' if len(unmatched) > 10 else ''}"
                )
        except Exception:
            warnings.append("tree_file 校验时树解析失败，已跳过 ID 匹配检查")

    spec = TemplateSpec(template_type=kind, label=kind, data_rows=rows, separator="TAB")
    result = _finish(runtime, spec, output, force)
    result.warnings.extend(warnings)
    return result


def _bundle_impl(
    runtime: Runtime,
    specs: list[dict] | None,
    bundle_name: str,
    tree_file: str | None,
    tree: str | None,
    taxonomy_file: str | None,
    taxonomy: str | None,
) -> ToolResult:
    if not specs:
        raise UsageError("参数 specs 必填：模板规格 JSON 数组（每个元素必含 template_type）")
    tree_text = resolve_tree_text(runtime, tree=tree, tree_file=tree_file, required=False)
    tax_text = resolve_table_text(
        runtime, inline=taxonomy, table_file=taxonomy_file, required=False, group_name="分类表"
    )

    built: list[TemplateSpec] = []
    for idx, item in enumerate(specs, start=1):
        if not isinstance(item, dict) or not item.get("template_type"):
            raise UsageError(f"specs[{idx}] 缺少 template_type")
        get_template_type(item["template_type"])
        ts = TemplateSpec(
            template_type=str(item["template_type"]),
            label=str(item.get("label") or item["template_type"]),
            separator=str(item.get("separator") or "TAB"),
            parameters=dict(item.get("parameters") or {}),
        )
        ts.color = validate_color(str(item.get("color") or "#ff0000"))
        if item.get("data_rows"):
            ts.data_rows = [dict(r) for r in item["data_rows"] if isinstance(r, dict)]
        elif item.get("table_file"):
            text = runtime.workspace.read_text(
                str(item["table_file"]), max_bytes=runtime.config.max_file_bytes
            )
            ts.data_rows = table_to_rows(text)
        elif tree_text and tax_text:
            ts.tree = tree_text
            ts.taxonomy = tax_text
            ts.column = item.get("column")
            ts.palette = item.get("palette")
            ts.id_column = str(item.get("id_column") or "id")
        built.append(ts)

    data = create_templates_bundle(built, runtime.workspace, bundle_name=bundle_name)
    files = [{"path": f, "kind": "template"} for f in data["files"]]
    return ToolResult.ok(
        f"批量模板生成完成：{data['n_templates']} 个，写入 templates/{bundle_name}/",
        data,
        files=files,
    )


def _validate_impl(
    runtime: Runtime,
    template: str | None,
    template_file: str | None,
    tree: str | None,
    tree_file: str | None,
) -> ToolResult:
    tpl_text = resolve_table_text(
        runtime, inline=template, table_file=template_file, required=True, group_name="模板"
    )
    tree_text = resolve_tree_text(runtime, tree=tree, tree_file=tree_file, required=False)
    result = validate_template(tpl_text, tree_text=tree_text)  # type: ignore[arg-type]
    data = {
        "valid": result["valid"],
        "header": result["header"],
        "n_data_rows": result["n_data_rows"],
        "checks": result["checks"],
        "matched_ids": result.get("matched_ids"),
        "unmatched_ids_preview": result.get("unmatched_ids_preview", []),
    }
    msg = "模板校验通过" if result["valid"] else "模板存在 CRITICAL 问题，请按 checks 修正"
    return ToolResult.ok(msg, data)
