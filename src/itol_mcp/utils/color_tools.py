"""配色工具：色盲友好调色板、类别取色、hex 校验。"""

from __future__ import annotations

import re

from itol_mcp.exceptions import TemplateError

# 5 套预置调色板（附录 A.3）
PALETTES: dict[str, tuple[str, ...]] = {
    "tol_bright": ("#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE", "#AA3377", "#BBBBBB"),
    "tol_vibrant": ("#EE7733", "#0077BB", "#33BBEE", "#EE3377", "#CC3311", "#009988", "#BBBBBB"),
    "wong": (
        "#000000",
        "#E69F00",
        "#56B4E9",
        "#009E73",
        "#F0E442",
        "#0072B2",
        "#D55E00",
        "#CC79A7",
    ),
    "okabeito": (
        "#E69F00",
        "#56B4E9",
        "#009E73",
        "#F0E442",
        "#0072B2",
        "#D55E00",
        "#CC79A7",
        "#000000",
    ),
    "ibm": ("#648FFF", "#785EF0", "#DC267F", "#FE6100", "#FFB000"),
}

# 合法命名色白名单（iTOL 支持常用 HTML 颜色名，此处收录常用子集）
_NAMED_COLORS: dict[str, str] = {
    "black": "#000000",
    "white": "#FFFFFF",
    "red": "#FF0000",
    "green": "#00FF00",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "orange": "#FFA500",
    "purple": "#800080",
    "grey": "#808080",
    "gray": "#808080",
    "brown": "#A52A2A",
    "pink": "#FFC0CB",
    "teal": "#008080",
    "navy": "#000080",
}

_HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def validate_color(hex_or_name: str) -> str:
    """校验并规范化颜色值：``#RRGGBB`` / ``#RRGGBBAA`` / ``#RGB`` / 命名色。

    非法颜色抛 ``TemplateError``（防注入）。
    """
    value = str(hex_or_name).strip()
    if not value:
        raise TemplateError("颜色值不能为空")
    if value.lower() in _NAMED_COLORS:
        return _NAMED_COLORS[value.lower()]
    if _HEX_RE.match(value):
        return value.upper()
    raise TemplateError(
        f"非法颜色值：{value!r}（支持 #RRGGBB/#RRGGBBAA/#RGB 或命名色："
        f"{', '.join(sorted(_NAMED_COLORS))}）"
    )


def assign_colors(
    categories: list[str],
    palette: str | None = None,
    explicit: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    """为类别列表分配颜色。

    返回 ``(colors, warnings)``：
    - ``explicit`` 显式映射优先（未命中类别回落到 palette）；
    - 类别数超过 palette 色数时循环取色并给出 WARNING。
    """
    palette_name = palette or "tol_bright"
    if palette_name not in PALETTES:
        raise TemplateError(f"未知配色方案：{palette_name}（可用：{', '.join(PALETTES)}）")
    base = PALETTES[palette_name]
    colors: list[str] = []
    warnings: list[str] = []
    seen_categories: dict[str, int] = {}
    for cat in categories:
        key = str(cat)
        if explicit and key in explicit:
            colors.append(validate_color(explicit[key]))
            continue
        idx = seen_categories.setdefault(key, len(seen_categories))
        if seen_categories[key] >= len(base):
            warnings.append(f"类别数超过配色方案 {palette_name} 的色数（{len(base)}），已循环取色")
        colors.append(base[idx % len(base)])
    return colors, warnings


def build_category_color_map(
    values: list[str],
    palette: str | None = None,
    explicit: dict[str, str] | None = None,
) -> tuple[dict[str, str], list[str]]:
    """构建「类别 → 颜色」映射，返回 ``(mapping, warnings)``。"""
    categories: list[str] = []
    for v in values:
        if v not in categories:
            categories.append(str(v))
    colors, warnings = assign_colors(categories, palette, explicit)
    return dict(zip(categories, colors, strict=True)), warnings
