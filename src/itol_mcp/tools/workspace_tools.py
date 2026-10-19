"""组 A：工作区与文件工具（工具 1–3，见《04 §4.2》）。"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from itol_mcp.tools.common import MCPServerLike, Runtime, execute, preview_lines
from itol_mcp.utils.result import ToolResult

# 文件预览行数合法区间（1–5000）
HEAD_LINES = Annotated[int, Field(ge=1, le=5000, description="预览行数上限（1–5000，默认 200）")]


def register(server: MCPServerLike, runtime: Runtime) -> None:
    """向 MCP 服务器注册工作区工具。"""

    @server.tool(
        name="itol_workspace_list",
        description=(
            "列出 iTOL-MCP 工作区目录内容（默认根目录，可指定工作区内相对子目录，如 data、templates、exports）。"
            "返回文件清单 [{name, path, size, kind}]，kind 按扩展名推断：dir/tree/table/template/image/other。"
            "用于确认可供后续工具使用的文件。"
        ),
    )
    def itol_workspace_list(subdir: str = "") -> dict:
        """列出工作区目录内容。"""
        return execute(
            runtime.logger,
            "itol_workspace_list",
            lambda: _workspace_list_impl(runtime, subdir),
        )

    @server.tool(
        name="itol_file_read",
        description=(
            "读取工作区内文本文件（树/表格/模板/配置），返回前 N 行与总行数。"
            "超过 1MB 的文件将被拒绝，提示改用工作区直连或拆分处理。"
            "参数 path 为工作区内相对路径（如 data/tree.nwk）。"
        ),
    )
    def itol_file_read(path: str, head_lines: HEAD_LINES = 200) -> dict:
        """读取工作区内文本文件（预览前 N 行）。"""
        return execute(
            runtime.logger,
            "itol_file_read",
            lambda: _file_read_impl(runtime, path, head_lines),
        )

    @server.tool(
        name="itol_file_write",
        description=(
            "将文本内容写入工作区文件（树内容、CSV/TSV 表格、iTOL 模板文本、任意辅助文件）。"
            "安全约束：拒绝写入 .itolapi.key、隐藏文件与工作区外路径；force=false 时文件已存在将报错。"
            "参数 path 为工作区内相对路径（如 data/tree.nwk、templates/strip.txt）。"
        ),
    )
    def itol_file_write(path: str, content: str, force: bool = False) -> dict:
        """写入文本到工作区文件（UTF-8）。"""
        return execute(
            runtime.logger,
            "itol_file_write",
            lambda: _file_write_impl(runtime, path, content, force),
        )


# ---------------------------------------------------------------------------
# 实现
# ---------------------------------------------------------------------------


def _workspace_list_impl(runtime: Runtime, subdir: str) -> ToolResult:
    entries = runtime.workspace.list(subdir or "")
    files = [
        {"name": e["name"], "path": e["path"], "size": e["size"], "kind": e["kind"]}
        for e in entries
    ]
    data = {
        "files": files,
        "count": len(files),
        "workspace_dir": str(runtime.workspace.root),
        "subdir": subdir or ".",
    }
    return ToolResult.ok(f"工作区「{subdir or '.'}」共 {len(files)} 个条目", data)


def _file_read_impl(runtime: Runtime, path: str, head_lines: int) -> ToolResult:
    from itol_mcp.tools.common import PREVIEW_MAX_BYTES

    text = runtime.workspace.read_text(path, max_bytes=PREVIEW_MAX_BYTES)
    lines = text.splitlines()
    total = len(lines)
    shown = lines[:head_lines]
    if total > head_lines:
        shown = shown + [f"…（文件共 {total} 行，仅显示前 {head_lines} 行）"]
    data = {
        "path": str(runtime.workspace.resolve(path)),
        "total_lines": total,
        "content": "\n".join(shown),
        "truncated": total > head_lines,
    }
    return ToolResult.ok(
        f"已读取 {path}（共 {total} 行，预览前 {min(head_lines, total)} 行）", data
    )


def _file_write_impl(runtime: Runtime, path: str, content: str, force: bool) -> ToolResult:
    real = runtime.workspace.write_text(path, content, force=force)
    n_bytes = len(content.encode("utf-8"))
    data = {"path": str(real), "bytes": n_bytes, "written": True}
    return ToolResult.ok(
        f"已写入 {path}（{n_bytes} 字节）", data, files=[_file_entry(real, content)]
    )


def _file_entry(path: object, content: str) -> dict:
    return {
        "path": str(path),
        "kind": "other",
        "bytes": len(content.encode("utf-8")),
        "text_preview": preview_lines(content, 40),
    }
