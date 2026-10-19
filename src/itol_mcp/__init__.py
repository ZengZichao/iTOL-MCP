"""iTOL-MCP：基于 MCP（Model Context Protocol）的 iTOL 可视化自动化服务端。

本项目将 iTOL 的树解析、分类学分析、注释模板生成与批量上传/导出能力封装为
标准 MCP 工具，使各类 AI 助手（Claude Desktop、Cursor、CatPaw、Claude Code 等）
可通过对话自主完成「系统发育树检查 → 分类学与单系群分析 → iTOL 注释模板生成 →
上传 iTOL → 导出成果物」的全流程。

典型用法：
    from itol_mcp import build_server

    server = build_server()
    server.run(transport="stdio")
"""

from itol_mcp._version import __version__
from itol_mcp.server import build_server, main, run

__all__ = ["__version__", "build_server", "main", "run"]
