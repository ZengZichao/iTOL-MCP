"""模板服务：类型注册表 + 统一渲染器 + 打包 + 校验（实现设计第 5.6 节）。

类型清单与《附录A》一致：32 种模板类型（含别名），全部可通过统一入口
``itol_template_create`` 生成；快捷工具为参数预绑定形态。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from itol_mcp.exceptions import TemplateError, TemplateTypeError
from itol_mcp.services.workspace_service import Workspace
from itol_mcp.utils.color_tools import validate_color
from itol_mcp.utils.io import format_number

# ---------------------------------------------------------------------------
# 参数白名单（附录 A.2 + 通用参数）
# ---------------------------------------------------------------------------

_COMMON_PARAMS = (
    "DATASET_SCALE",
    "LEGEND_TITLE",
    "LEGEND_SHAPES",
    "LEGEND_COLORS",
    "LEGEND_LABELS",
    "LEGEND_POSITION",
    "DATASET_COLOR",
)

PARAMETER_WHITELIST: dict[str, tuple[str, ...]] = {
    "color_strip": _COMMON_PARAMS
    + ("STRIP_WIDTH", "MARGIN", "BORDER_COLOR", "HEIGHT_FACTOR", "COLOR_BRANCHES"),
    "heatmap": _COMMON_PARAMS
    + (
        "FIELD_LABELS",
        "WIDTH",
        "STRIP_WIDTH",
        "SHOW_STRIP_LABELS",
        "INTERNAL_STRIP_WIDTH",
        "BLOCKS",
        "MOUSE_OVER",
        "GRADIENT",
        "COLOR_MIN",
        "COLOR_MAX",
        "COLOR_MID",
        "USE_MID_COLOR",
    ),
    "simple_bar": _COMMON_PARAMS
    + ("MINIMUM", "MAXIMUM", "BAR_WIDTH", "FILL_FRACTION", "FILL_COLOR", "BAR_COLOR"),
    "multi_bar": _COMMON_PARAMS
    + ("FIELD_LABELS", "WIDTH", "COLORS", "HEIGHT_FACTOR", "ALIGN_FIELDS", "FIELD_ALIGN"),
    "binary": _COMMON_PARAMS + ("STRIP_WIDTH", "COLORS", "BORDER_COLOR", "FIELD_LABELS"),
    "gradient": _COMMON_PARAMS
    + ("STRIP_WIDTH", "MARGIN", "COLOR_MIN", "COLOR_MAX", "COLOR_MID", "USE_MID_COLOR"),
    "symbols": _COMMON_PARAMS + ("SIZE", "SHAPE", "POSITION", "SYMBOL_SPACING", "COLOR"),
    "pie_chart": _COMMON_PARAMS + ("SIZE", "COLORS", "SHOW_LABELS", "ALIGN_LABELS", "PIE_SIZE"),
    "externalshape": _COMMON_PARAMS + ("TYPE", "SIZE", "POSITION", "SHOW_LABELS", "SHAPE_TYPE"),
    "text": _COMMON_PARAMS
    + ("FONT_SIZE", "FONT_COLOR", "BACKGROUND_COLOR", "PADDING_X", "PADDING_Y"),
    "boxplot": _COMMON_PARAMS
    + ("WIDTH", "COLOR", "EXTREME_VALUE_COLOR", "EXTREME_SIZE", "MINIMUM", "MAXIMUM"),
    "domains": _COMMON_PARAMS
    + ("STROKE_WIDTH", "MARGIN", "USE_MID_LINE", "GRADIENT", "DOMAIN_COLORS", "DOMAIN_LABELS"),
    "arrows": _COMMON_PARAMS
    + ("HEAD_COLOR", "BODY_COLOR", "HEAD_SIZE", "BODY_SIZE", "SIZE", "POSITION"),
    "connections": _COMMON_PARAMS
    + ("CURVE", "CURVATURE", "CONNECTION_TYPE", "LINE_WIDTH", "COLOR", "FORMAT"),
    "tanglegram": _COMMON_PARAMS,
    "line_chart": _COMMON_PARAMS
    + ("WIDTH", "MINIMUM", "MAXIMUM", "GROUP_COLORS", "GROUP_LABELS", "SHOW_INTERNAL"),
    "image": _COMMON_PARAMS + ("WIDTH", "HEIGHT", "X_SHIFT", "Y_SHIFT"),
    "alignment": _COMMON_PARAMS
    + ("HEIGHT", "WIDTH", "SHOW_NAMES", "ALIGN_CHARS", "BAR_BACKGROUND"),
    "placement": _COMMON_PARAMS,
    "timescale": (
        "TIMESCALE_LABEL",
        "TIMESCALE_AUTO",
        "TIMESCALE_EXPONENT_SHIFT",
        "TIMESCALE_ALIGN",
    ),
    "meme": _COMMON_PARAMS
    + (
        "STROKE_WIDTH",
        "MYGENE_STROKE",
        "MYGENE_STROKE_WIDTH",
        "MYGENE_MARGIN",
        "MYGENE_SCALE",
        "MYGENE_BGCOLOR",
        "MYGENE_FGCOLOR",
        "DOMAIN_COLORS",
    ),
    "manual": _COMMON_PARAMS,
    "labels": ("SHOW_INTERNAL", "BOLD_LABELS", "COLOR", "FONT_SIZE", "SHOW_LABELS"),
    "popup_info": (),
    "tree_colors": (
        "STRIP_WIDTH",
        "STRIP_COLOR",
        "NODE_FORMAT",
        "NODE_SHAPE",
        "NODE_SIZE",
        "NODE_COLOR",
    ),
    "range": _COMMON_PARAMS + ("RANGE_COLORS", "EFFICIENCY", "FILL", "COLOR", "STROKE", "WIDTH"),
    "style": _COMMON_PARAMS,
    "collapse": (),
    "prune": (),
    "spacing": (),
    "treestyle": ("STYLE", "WIDTH", "COLOR"),
    "my_dataset": _COMMON_PARAMS,
}


# ---------------------------------------------------------------------------
# 类型注册表
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemplateTypeInfo:
    """模板类型元信息（与《附录A》一致）。"""

    type_name: str
    header: str
    required_columns: tuple[str, ...]
    supports_label_color: bool = True
    aliases: tuple[str, ...] = ()
    value_columns: tuple[str, ...] = ()  # 固定列序；空 = id + 其余键（动态多列）
    is_dataset: bool = (
        True  # False：LABELS/POPUP_INFO/TREE_COLORS/COLLAPSE/PRUNE/SPACING（无 DATA 标记）
    )


_TEMPLATE_REGISTRY: dict[str, TemplateTypeInfo] = {}


def register_template(
    type_name: str,
    header: str,
    required_columns: tuple[str, ...] = (),
    supports_label_color: bool = True,
    aliases: tuple[str, ...] = (),
    value_columns: tuple[str, ...] = (),
    is_dataset: bool = True,
) -> None:
    """注册模板类型（可被测试重复调用，先移除旧条目）。"""
    _TEMPLATE_REGISTRY.pop(type_name, None)
    info = TemplateTypeInfo(
        type_name=type_name,
        header=header,
        required_columns=required_columns,
        supports_label_color=supports_label_color,
        aliases=aliases,
        value_columns=value_columns,
        is_dataset=is_dataset,
    )
    _TEMPLATE_REGISTRY[type_name] = info


def _register_all() -> None:
    """注册全部 32 种类型（幂等）。"""
    if _TEMPLATE_REGISTRY:
        return
    # id, value, color
    register_template(
        "color_strip",
        "DATASET_COLORSTRIP",
        ("id", "value", "color"),
        aliases=("colorstrip",),
        value_columns=("id", "value", "color"),
    )
    register_template("heatmap", "DATASET_HEATMAP", ("id",), value_columns=("id",))
    register_template(
        "simple_bar",
        "DATASET_SIMPLEBAR",
        ("id", "bar_height"),
        aliases=("simplebar",),
        value_columns=("id", "bar_height"),
    )
    register_template(
        "multi_bar", "DATASET_MULTIBAR", ("id",), aliases=("multibar",), value_columns=("id",)
    )
    register_template("binary", "DATASET_BINARY", ("id",), value_columns=("id",))
    register_template(
        "gradient", "DATASET_GRADIENT", ("id", "value"), value_columns=("id", "value")
    )
    register_template(
        "symbols",
        "DATASET_SYMBOL",
        ("id", "type", "value", "color"),
        aliases=("symbol",),
        value_columns=("id", "type", "value", "color"),
    )
    register_template(
        "pie_chart", "DATASET_PIECHART", ("id",), aliases=("piechart",), value_columns=("id",)
    )
    register_template(
        "externalshape",
        "DATASET_EXTERNALSHAPE",
        ("id",),
        aliases=("external-shape", "external-shape-bubble", "external_shape"),
        value_columns=("id", "value", "color"),
        is_dataset=True,
    )
    register_template("text", "DATASET_TEXT", ("id", "text"), value_columns=("id", "text"))
    register_template(
        "boxplot",
        "DATASET_BOXPLOT",
        ("id", "minimum", "q1", "median", "q3", "maximum"),
        value_columns=("id", "minimum", "q1", "median", "q3", "maximum"),
    )
    register_template(
        "domains",
        "DATASET_DOMAINS",
        ("id", "from", "to", "type"),
        value_columns=("id", "from", "to", "type"),
    )
    register_template(
        "arrows",
        "DATASET_ARROWS",
        ("id", "position"),
        aliases=("arrow",),
        value_columns=("id", "position"),
    )
    register_template(
        "connections",
        "DATASET_CONNECTION",
        ("id1", "id2"),
        aliases=("connection",),
        value_columns=("id1", "id2"),
    )
    register_template(
        "tanglegram", "DATASET_TANGLEGRAM", ("id1", "id2"), value_columns=("id1", "id2")
    )
    register_template(
        "line_chart",
        "DATASET_LINECHART",
        ("id", "position", "value"),
        aliases=("linechart",),
        value_columns=("id", "position", "value"),
    )
    register_template(
        "image", "DATASET_IMAGE", ("id", "image_file"), value_columns=("id", "image_file")
    )
    register_template(
        "alignment", "DATASET_ALIGNMENT", ("id", "alignment"), value_columns=("id", "alignment")
    )
    register_template(
        "placement",
        "DATASET_PLACEMENT",
        ("id", "position", "count"),
        value_columns=("id", "position", "count"),
    )
    register_template(
        "timescale",
        "DATASET_TIMESCALE",
        ("time_point", "label"),
        supports_label_color=False,
        value_columns=("time_point", "label"),
    )
    register_template(
        "meme",
        "DATASET_MEME",
        ("id", "start", "end", "name"),
        value_columns=("id", "start", "end", "name"),
    )
    register_template("manual", "DATASET_MANUAL", (), supports_label_color=True, value_columns=())
    register_template(
        "labels",
        "LABELS",
        ("id", "label"),
        supports_label_color=False,
        value_columns=("id", "label"),
        is_dataset=False,
    )
    register_template(
        "popup_info",
        "POPUP_INFO",
        ("id", "title", "content"),
        supports_label_color=False,
        value_columns=("id", "title", "content"),
        is_dataset=False,
    )
    register_template(
        "tree_colors",
        "TREE_COLORS",
        ("id", "type", "color"),
        supports_label_color=False,
        value_columns=("id", "type", "color"),
        is_dataset=False,
    )
    register_template(
        "range", "DATASET_RANGE", ("id", "label", "color"), value_columns=("id", "label", "color")
    )
    register_template(
        "style", "DATASET_STYLE", ("id", "type", "color"), value_columns=("id", "type", "color")
    )
    register_template(
        "collapse",
        "COLLAPSE",
        ("id",),
        supports_label_color=False,
        value_columns=("id",),
        is_dataset=False,
    )
    register_template(
        "prune",
        "PRUNE",
        ("id",),
        supports_label_color=False,
        value_columns=("id",),
        is_dataset=False,
    )
    register_template(
        "spacing",
        "SPACING",
        ("id", "factor"),
        supports_label_color=False,
        value_columns=("id", "factor"),
        is_dataset=False,
    )
    register_template(
        "treestyle",
        "DATASET_TREESTYLE",
        ("id", "type", "style"),
        value_columns=("id", "type", "style"),
    )
    register_template(
        "my_dataset",
        "DATASET_MYDATASET",
        ("id", "value"),
        aliases=("mydataset",),
        value_columns=("id", "value"),
    )


_register_all()


def list_template_types() -> list[dict]:
    """列出全部模板类型（机器可读）。"""
    return [
        {
            "type_name": info.type_name,
            "header": info.header,
            "required_columns": list(info.required_columns),
            "aliases": list(info.aliases),
            "is_dataset": info.is_dataset,
            "key_parameters": list(PARAMETER_WHITELIST.get(info.type_name, ())),
        }
        for info in _TEMPLATE_REGISTRY.values()
    ]


def get_template_type(name: str) -> TemplateTypeInfo:
    """按类型名或别名查找；未知类型抛 ``TemplateTypeError``。"""
    key = str(name).strip().lower()
    if key in _TEMPLATE_REGISTRY:
        return _TEMPLATE_REGISTRY[key]
    for info in _TEMPLATE_REGISTRY.values():
        if key in info.aliases:
            return info
    available = ", ".join(sorted(_TEMPLATE_REGISTRY))
    raise TemplateTypeError(f"不支持的模板类型：{name!r}（可用类型：{available}）")


# ---------------------------------------------------------------------------
# 渲染器
# ---------------------------------------------------------------------------

_SEPARATOR_CHARS = {"TAB": "\t", "SPACE": " ", "COMMA": ","}


@dataclass
class TemplateSpec:
    """模板生成规格。"""

    template_type: str
    label: str = ""
    color: str = "#ff0000"
    separator: str = "TAB"
    data_rows: list[dict] = field(default_factory=list)
    parameters: dict = field(default_factory=dict)
    tree: str | None = None
    taxonomy: str | None = None
    column: str | None = None
    palette: str | None = None
    id_column: str = "id"


def _normalize_separator(sep: str) -> str:
    sep = (sep or "TAB").strip().upper()
    if sep not in _SEPARATOR_CHARS:
        raise TemplateError(f"非法分隔符：{sep}（可选 TAB/SPACE/COMMA）")
    return sep


def _normalize_row_keys(info: TemplateTypeInfo, row: dict) -> dict:
    """行键别名归一（source1→id1 等）。"""
    out = dict(row)
    if "source1" in out and "id1" not in out:
        out["id1"] = out.pop("source1")
    if "source2" in out and "id2" not in out:
        out["id2"] = out.pop("source2")
    if "bar_height" not in out and "value" in out and info.type_name == "simple_bar":
        out["bar_height"] = out["value"]
    return out


def _ordered_columns(info: TemplateTypeInfo, first_row: dict) -> list[str]:
    """确定数据行输出列序。

    固定列（``value_columns``，如 boxplot 的五分位列）之后的额外键
    （连接线 width/color、箱线图 extreme 列、域架构 fill_color 等）按插入顺序追加，
    与 iTOL「仅需匹配必需列、可携带额外列」的规范保持一致。
    """
    base = list(info.value_columns) if info.value_columns else ["id"]
    for key in first_row:
        if key not in base:
            base.append(key)
    return base


def _cell_value(info: TemplateTypeInfo, col: str, row: dict, spec: TemplateSpec) -> str:
    """取单元格值，缺失时按类型默认补全。"""
    raw = row.get(col)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        # 类型专属默认
        if col == "type" and info.type_name == "symbols":
            return str(spec.parameters.get("SHAPE", spec.parameters.get("TYPE", "2")))
        if col == "type" and info.type_name in ("tree_colors", "style", "treestyle"):
            defaults = {"tree_colors": "label", "style": "branch", "treestyle": "label"}
            return defaults.get(info.type_name, "")
        if col == "color" and info.supports_label_color:
            return validate_color(spec.color)
        if col == "value" and info.type_name == "color_strip":
            return str(row.get("id", ""))
        if col == "collapse" and info.type_name == "collapse":
            return "1"
        if col == "factor" and info.type_name == "spacing":
            return "1.0"
        if col == "style" and info.type_name == "treestyle":
            return "normal"
        if col == "width" and info.type_name in ("treestyle", "tree_colors"):
            return "2"
        return ""
    if col == "color":
        return validate_color(raw)  # 统一规范化/校验色值（含大写化，兼容 tree_colors 等）
    if isinstance(raw, (int, float)) or (isinstance(raw, str) and _is_numeric(raw)):
        return format_number(raw)
    return str(raw).strip()


def _is_numeric(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _validate_required(info: TemplateTypeInfo, rows: list[dict]) -> None:
    """必填列校验：rows 为空或缺少必填键时报错。"""
    if not rows:
        raise TemplateError(
            f"模板类型 {info.type_name}（{info.header}）缺少数据行（data_rows/table_file 为空）"
        )
    first = rows[0]
    missing = [c for c in info.required_columns if c not in first and not _has_default(info, c)]
    if missing:
        raise TemplateError(
            f"模板类型 {info.type_name}（{info.header}）缺少必需列：{missing}；"
            f"数据行现有键：{list(first.keys())}"
        )


def _has_default(info: TemplateTypeInfo, col: str) -> bool:
    """该列是否有渲染期默认值（无需在数据行中提供）。"""
    if col == "color" and info.supports_label_color:
        return True
    if info.type_name == "symbols" and col == "type":
        return True
    if info.type_name in ("tree_colors", "style", "treestyle") and col == "type":
        return True
    if info.type_name == "treestyle" and col == "style":
        return True
    if info.type_name in ("collapse",) and col == "collapse":
        return True
    if info.type_name == "spacing" and col == "factor":
        return True
    return col == "width" and info.type_name in ("treestyle", "tree_colors")


def render_template(spec: TemplateSpec) -> tuple[str, list[str]]:
    """渲染模板文本，返回 ``(text, warnings)``。"""
    info = get_template_type(spec.template_type)
    sep = _normalize_separator(spec.separator)
    sep_char = _SEPARATOR_CHARS[sep]

    # 数据行来源：分类学驱动 > 显式 data_rows
    rows, warnings = _maybe_taxonomy_rows(spec, info)
    if not rows:
        rows = list(spec.data_rows)
    normalized: list[dict] = [_normalize_row_keys(info, row) for row in rows]
    _validate_required(info, normalized)

    lines = [info.header, f"SEPARATOR {sep}"]

    label = spec.label or info.type_name
    if info.is_dataset:
        lines.append(f"DATASET_LABEL {label}")
        if info.supports_label_color and spec.color:
            lines.append(f"COLOR {validate_color(spec.color)}")

    allowed = set(PARAMETER_WHITELIST.get(info.type_name, ()))
    for key, value in spec.parameters.items():
        key_s = str(key).strip()
        if key_s not in allowed:
            warnings.append(f"参数 {key_s} 不在类型 {info.type_name} 的白名单中，已忽略")
            continue
        lines.append(f"{key_s} {_format_param(value)}")

    if info.is_dataset:
        lines.append("DATA")

    # 数据行
    first_row = normalized[0] if normalized else {}
    columns = _ordered_columns(info, first_row)
    for row in normalized:
        cells = [_cell_value(info, col, row, spec) for col in columns]
        lines.append(sep_char.join(cells))

    return "\n".join(lines) + "\n", warnings


def _format_param(value: object) -> str:
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    if isinstance(value, dict):
        return str(value)
    return format_number(value)


def _maybe_taxonomy_rows(
    spec: TemplateSpec, info: TemplateTypeInfo
) -> tuple[list[dict], list[str]]:
    """分类学驱动渲染：tree+taxonomy+column 存在时构建数据行。

    返回 ``(data_rows, warnings)``；未启用分类学驱动时返回 (None, [])。
    """
    if not (spec.tree and spec.taxonomy and spec.column):
        return [], []
    import pandas as pd

    from itol_mcp.services.taxonomy_service import (
        build_color_strip_rows,
        load_taxonomy_table,
        numeric_column_values,
    )

    warnings: list[str] = []
    id_col = spec.id_column or "id"
    if info.type_name == "color_strip":
        rows, w = build_color_strip_rows(
            spec.tree, spec.taxonomy, id_col, spec.column, spec.palette, None
        )
        warnings.extend(w)
        return rows, warnings

    # 检测列是否为数值列
    df = load_taxonomy_table(spec.taxonomy, id_column=id_col)
    col_vals = df[spec.column].astype(str).tolist() if spec.column in df.columns else []
    numeric = pd.to_numeric(
        pd.Series([v for v in col_vals if v.strip() != ""]), errors="coerce"
    ).dropna()
    try:
        numerics = numeric_column_values(spec.tree, spec.taxonomy, id_col, spec.column)
    except TemplateError:
        numerics = []
    if info.type_name == "gradient":
        if len(numeric) == 0:
            raise TemplateError(f"模板类型 gradient 需要数值列，但列 {spec.column!r} 不是数值")
        vmin, vmax = float(numeric.min()), float(numeric.max())
        rows = []
        for i, v in numerics:
            norm = 0.0 if vmax == vmin else (v - vmin) / (vmax - vmin)
            rows.append({"id": i, "value": round(norm, 6)})
        return rows, warnings
    if info.type_name == "simple_bar":
        return [{"id": i, "bar_height": v} for i, v in numerics], warnings
    if info.type_name == "heatmap":
        return [{"id": i, "value": v} for i, v in numerics], warnings
    if info.type_name == "binary":
        # 类别 → 1/0 二值列
        categories = sorted({v for v in col_vals if v.strip()})
        if len(categories) > 20:
            warnings.append(f"类别数过多（{len(categories)}），binary 仅输出前 20 列")
            categories = categories[:20]
        bin_rows: list[dict] = []
        for _, row in df.iterrows():
            entry: dict = {"id": str(row[id_col])}
            for cat in categories:
                entry[cat] = 1 if str(row[spec.column]).strip() == cat else 0
            bin_rows.append(entry)
        return bin_rows, warnings
    warnings.append(
        f"列 {spec.column!r} 对类型 {info.type_name} 缺少直接映射，已按类别 id/value 输出"
    )
    rows = []
    for _, row in df.iterrows():
        rows.append({"id": str(row[id_col]), "value": str(row[spec.column]).strip()})
    return rows, warnings


# ---------------------------------------------------------------------------
# 文件输出与打包
# ---------------------------------------------------------------------------


def create_template(
    spec: TemplateSpec, workspace: Workspace, out_path: str | None = None, force: bool = False
) -> dict:
    """渲染并写入模板文件，返回结果 dict。"""
    text, warnings = render_template(spec)
    info = get_template_type(spec.template_type)
    if not out_path:
        counter = 1
        base = f"{info.type_name}"
        while (workspace.root / "templates" / f"{base}_{counter}.txt").exists():
            counter += 1
        out_path = f"templates/{base}_{counter}.txt"
    workspace.write_text(out_path, text, force=force)
    file_abs = workspace.resolve(out_path)
    return {
        "template_type": info.type_name,
        "header": info.header,
        "n_rows": len(spec.data_rows) if spec.data_rows else 0,
        "label": spec.label or info.type_name,
        "file": str(file_abs),
        "warnings": warnings,
    }


def create_templates_bundle(
    specs: list[TemplateSpec],
    workspace: Workspace,
    out_dir: str | None = None,
    bundle_name: str = "bundle",
) -> dict:
    """一次生成多个模板（写入统一目录），返回 ``{n_templates, files: [路径…]}``。"""
    if not specs:
        raise TemplateError("模板打包失败：specs 为空")
    out_dir = out_dir or f"templates/{bundle_name}"
    created: list[dict] = []
    for idx, spec in enumerate(specs, start=1):
        info = get_template_type(spec.template_type)
        text, warnings = render_template(spec)
        out_path = f"{out_dir}/{idx:02d}_{info.type_name}.txt"
        workspace.write_text(out_path, text, force=True)
        created.append(
            {
                "output": str(workspace.resolve(out_path)),
                "template_type": info.type_name,
                "n_rows": len(spec.data_rows) if spec.data_rows else 0,
                "warnings": warnings,
            }
        )
    return {"n_templates": len(created), "files": [c["output"] for c in created]}


# ---------------------------------------------------------------------------
# 模板校验（工具 24）
# ---------------------------------------------------------------------------


def validate_template(template_text: str, tree_text: str | None = None) -> dict:
    """校验模板文本是否符合 iTOL 注释文件规范。

    检查项：头部、分隔符、DATA 段、行内列数一致性、色值、ID 与树匹配度。
    """
    checks: list[dict] = []
    if not template_text.strip():
        return {
            "valid": False,
            "header": None,
            "n_data_rows": 0,
            "checks": [{"level": "CRITICAL", "message": "模板内容为空"}],
        }

    lines = template_text.splitlines()
    header = lines[0].strip()
    if not (
        header.startswith("DATASET_")
        or header in ("LABELS", "POPUP_INFO", "TREE_COLORS", "COLLAPSE", "PRUNE", "SPACING")
    ):
        checks.append({"level": "CRITICAL", "message": f"首行不是合法模板头部：{header!r}"})
        return {"valid": False, "header": header, "n_data_rows": 0, "checks": checks}

    checks.append({"level": "PASS", "message": f"头部 {header} 合法"})
    is_dataset = header.startswith("DATASET_")

    sep_line = ""
    sep_char = "\t"
    for ln in lines[1:]:
        if ln.startswith("SEPARATOR "):
            sep_line = ln
            token = ln.split(None, 1)[1].strip().upper()
            if token not in ("TAB", "SPACE", "COMMA"):
                checks.append(
                    {"level": "CRITICAL", "message": f"非法分隔符：{token}（可选 TAB/SPACE/COMMA）"}
                )
            else:
                sep_char = {"TAB": "\t", "SPACE": " ", "COMMA": ","}[token]
                checks.append({"level": "PASS", "message": f"分隔符 {token} 合法"})
            break
    if not sep_line:
        checks.append({"level": "WARN", "message": "未声明 SEPARATOR，iTOL 默认按 TAB 解析"})

    # 色值检查（COLOR 行 / DATASET_COLOR）
    for ln in lines[1:]:
        if ln.startswith(("COLOR ", "DATASET_COLOR ")):
            color = ln.split(None, 1)[1].strip()
            try:
                validate_color(color)
            except TemplateError as exc:
                checks.append({"level": "CRITICAL", "message": f"非法色值 {color!r}：{exc}"})

    # 数据段
    data_start = -1
    for idx, ln in enumerate(lines):
        if ln.strip() == "DATA":
            data_start = idx
            break
    data_lines: list[str] = []
    if is_dataset:
        if data_start < 0:
            checks.append({"level": "CRITICAL", "message": "DATASET_ 类型模板缺少 DATA 标记行"})
        else:
            data_lines = [ln for ln in lines[data_start + 1 :] if ln.strip()]
    else:
        # 非数据集类型：参数行之后的非头部行视为数据行
        data_lines = [
            ln
            for ln in lines[1:]
            if ln.strip()
            and not ln.startswith(
                (
                    "SEPARATOR",
                    "SHOW_",
                    "BOLD_",
                    "COLOR",
                    "FONT",
                    "STRIP",
                    "NODE",
                    "LEGEND",
                    "DATASET",
                )
            )
        ]

    if not data_lines:
        checks.append({"level": "WARN", "message": "模板没有数据行"})

    col_counts = {len(ln.split(sep_char)) for ln in data_lines}
    if len(col_counts) > 1:
        checks.append({"level": "CRITICAL", "message": f"数据行列数不一致：{sorted(col_counts)}"})
    else:
        checks.append(
            {
                "level": "PASS",
                "message": f"数据行 {len(data_lines)} 行，列数一致（{col_counts.pop() if col_counts else 0}）",
            }
        )

    # ID 与树匹配
    matched: int | None = None
    unmatched_preview: list[str] = []
    if tree_text:
        from itol_mcp.services.tree_service import parse_tree

        try:
            tree = parse_tree(tree_text)
        except Exception:
            tree = None
        if tree is not None:
            tree_ids = {n.taxon.label for n in tree.leaf_node_iter() if n.taxon and n.taxon.label}
            ids: list[str] = []
            for ln in data_lines:
                first = ln.split(sep_char, 1)[0].strip()
                if first and not first.replace(".", "").isdigit():
                    ids.append(first)
            matched = sum(1 for i in ids if i in tree_ids)
            unmatched = [i for i in ids if i not in tree_ids]
            unmatched_preview = unmatched[:10]
            if matched == len(ids):
                checks.append({"level": "PASS", "message": f"全部 {matched} 个 ID 与树匹配"})
            else:
                checks.append(
                    {
                        "level": "WARN",
                        "message": f"ID 匹配 {matched}/{len(ids)}，未匹配预览：{unmatched[:5]}",
                    }
                )

    valid = not any(c["level"] == "CRITICAL" for c in checks)
    return {
        "valid": valid,
        "header": header,
        "n_data_rows": len(data_lines),
        "checks": checks,
        "matched_ids": matched,
        "unmatched_ids_preview": unmatched_preview,
    }
