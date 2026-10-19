"""基础设施工具包：返回模型、日志、I/O、配色、常量。"""

from itol_mcp.utils.color_tools import (
    PALETTES,
    assign_colors,
    build_category_color_map,
    validate_color,
)
from itol_mcp.utils.result import ToolResult, truncate_preview

__all__ = [
    "PALETTES",
    "ToolResult",
    "assign_colors",
    "build_category_color_map",
    "truncate_preview",
    "validate_color",
]
