"""统一返回模型 ``ToolResult``（数据模型第 6.1 节）。

所有工具返回同一结构：
    {
        "success": bool,
        "message": str,
        "data": {...},
        "warnings": [...],
        "files": [...],
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolResult:
    """工具统一返回结构，字段与 MCP 协议兼容（dict 序列化）。"""

    success: bool
    message: str = ""
    data: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """序列化为客户端可消费的纯字典。"""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "warnings": list(self.warnings),
            "files": list(self.files),
        }

    @classmethod
    def ok(
        cls,
        message: str,
        data: dict | None = None,
        warnings: list[str] | None = None,
        files: list[dict] | None = None,
    ) -> ToolResult:
        """构造成功结果。"""
        return cls(
            success=True,
            message=message,
            data=data or {},
            warnings=warnings or [],
            files=files or [],
        )

    @classmethod
    def err(cls, message: str, warnings: list[str] | None = None) -> ToolResult:
        """构造失败结果。"""
        return cls(success=False, message=message, warnings=warnings or [])


def truncate_preview(text: str, limit: int = 2000) -> str:
    """将文本截断到指定长度（供 ``files[].text_preview`` 使用）。"""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n…（已截断，共 {len(text)} 字符）"
