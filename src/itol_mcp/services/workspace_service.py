"""工作区服务：文件访问白名单、原子写、输出路径消毒（实现设计第 5.3 节）。"""

from __future__ import annotations

import os
import re
from pathlib import Path

from itol_mcp.exceptions import WorkspaceError
from itol_mcp.utils.constants import KIND_BY_EXT
from itol_mcp.utils.io import atomic_write_text, read_text_file

# 禁止写入的文件名（工作区内）
_FORBIDDEN_NAMES = {".itolapi.key", ".git", ".hg", ".svn", "__pycache__"}
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class Workspace:
    """工作区根目录内的安全文件访问。

    所有路径解析规则：
    - ``~`` 展开、相对路径相对工作区根、绝对路径按原样；
    - 最终必须 ``is_relative_to(root)``（realpath 防 symlink 逃逸）；
    - 输出文件另做名称白名单校验（拒绝隐藏文件、``..``、控制字符）。
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for sub in ("templates", "exports", "data", "logs"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str | Path) -> Path:
        """将用户路径解析为工作区内的绝对路径；越界抛 ``WorkspaceError``。"""
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self.root / p
        real = p.resolve(strict=False)
        if not real.is_relative_to(self.root):
            raise WorkspaceError(
                f"路径越界：{p} 不在工作区 {self.root} 内。"
                "iTOL-MCP 仅允许访问工作区文件；请先将文件放入工作区或通过内联参数传内容"
            )
        return real

    def kind_for(self, path: Path) -> str:
        """按扩展名推断文件类别。"""
        name = path.name.lower()
        if name.endswith(".tree.txt"):
            return "tree"
        ext = path.suffix.lower()
        kind = KIND_BY_EXT.get(ext, "other")
        if kind == "tree" and name.endswith((".fasta", ".fa", ".faa", ".fna")):
            return "tree"
        if path.is_dir():
            return "dir"
        return kind

    def list(self, subdir: str = "") -> list[dict]:
        """列出工作区目录内容（递归一层），返回 ``[{name, path, size, kind}]``。"""
        target = self.resolve(subdir) if subdir else self.root
        if not target.is_dir():
            raise WorkspaceError(f"目录不存在：{target}")
        entries: list[dict] = []
        with os.scandir(target) as it:
            for entry in it:
                try:
                    entry_path = Path(entry.path)
                    if entry.is_dir(follow_symlinks=False) or entry.is_file(follow_symlinks=False):
                        kind = (
                            "dir"
                            if entry.is_dir(follow_symlinks=False)
                            else self.kind_for(entry_path)
                        )
                        entries.append(
                            {
                                "name": entry.name,
                                "path": str(entry_path.resolve()),
                                "size": entry.stat(follow_symlinks=False).st_size
                                if not entry.is_dir()
                                else 0,
                                "kind": kind,
                            }
                        )
                except OSError:
                    continue
        entries.sort(key=lambda e: (e["kind"] != "dir", e["name"].lower()))
        return entries

    def read_text(self, path: str | Path, max_bytes: int | None = None) -> str:
        """读取工作区内文本文件；超限抛 ``WorkspaceError``。"""
        real = self.resolve(path)
        return read_text_file(real, max_bytes=max_bytes)

    def write_text(self, path: str | Path, content: str, force: bool = False) -> Path:
        """原子写工作区内文本文件；``force=False`` 已存在即报错。"""
        real = self._validate_writable(path)
        return atomic_write_text(real, content, force=force)

    def path_for(self, name: str, subdir: str = "") -> Path:
        """规范化输出文件名（防路径穿越），返回工作区内绝对路径。

        - 拒绝绝对路径、``..`` 组件、空名、隐藏文件（``.`` 开头）、控制字符；
        - 允许 ``a/b.txt`` 形式的相对子路径（父目录自动创建）。
        """
        raw = str(name).strip()
        if not raw:
            raise WorkspaceError("输出文件名不能为空")
        if raw.startswith("/") or raw.startswith("~"):
            raise WorkspaceError(f"输出文件名不能是绝对路径：{raw}")
        if _CONTROL_RE.search(raw):
            raise WorkspaceError("输出文件名含控制字符")
        parts = raw.replace("\\", "/").split("/")
        for part in parts:
            if part in ("", ".", ".."):
                raise WorkspaceError(f"输出文件名含非法路径组件：{raw}")
            if part.startswith("."):
                raise WorkspaceError(f"输出文件名不允许隐藏文件（. 开头）：{raw}")
            if part in _FORBIDDEN_NAMES:
                raise WorkspaceError(f"禁止写入敏感文件：{raw}")
        target = self.resolve(subdir) if subdir else self.root
        out = (target / raw).resolve()
        if not out.is_relative_to(self.root):
            raise WorkspaceError(f"输出路径越界：{out}")
        return out

    def _validate_writable(self, path: str | Path) -> Path:
        """校验写入路径（隐藏文件与敏感路径拒绝）。"""
        p = Path(path).expanduser()
        if not p.is_absolute():
            real = self.resolve(p)
        else:
            real = p.resolve(strict=False)
            if not real.is_relative_to(self.root):
                raise WorkspaceError(f"路径越界：{real} 不在工作区 {self.root} 内")
        name = real.name
        if name in _FORBIDDEN_NAMES or name in {".itolapi.key"}:
            raise WorkspaceError(f"禁止写入敏感文件：{name}（密钥请使用配置密钥文件）")
        if name.startswith("."):
            raise WorkspaceError(f"禁止写入隐藏文件：{name}")
        rel = os.path.relpath(real, self.root)
        if any(part == ".." for part in Path(rel).parts):
            raise WorkspaceError(f"输出路径含非法组件：{path}")
        return real

    def abs_path(self, path: str | Path) -> Path:
        """供工具层向客户端展示的绝对路径。"""
        return self.resolve(path)
