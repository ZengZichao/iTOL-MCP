"""工具层共享：运行时上下文（Runtime）与通用参数解析辅助函数。

工具层职责（见《05 §5.8》）：
- 参数互斥校验（``tree`` vs ``tree_file`` 等）→ ``UsageError``（中文可读）；
- 调用服务层完成领域逻辑；
- 将 ``ItolMCPError`` 抑或未受控异常统一转为 ``ToolResult`` 字典。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar, overload

from itol_mcp.config import ServerConfig, resolve_api_key
from itol_mcp.exceptions import ItolMCPError, UsageError
from itol_mcp.services.api_service import ITOLClient
from itol_mcp.services.workspace_service import Workspace
from itol_mcp.utils.io import parse_table_text
from itol_mcp.utils.logger import get_logger
from itol_mcp.utils.result import ToolResult

# 单文件读取上限（1MB）：超过提示改用工作区直连（见工具 2 规范）
PREVIEW_MAX_BYTES = 1024 * 1024

_F = TypeVar("_F", bound=Callable[..., Any])


class MCPServerLike(Protocol):
    """MCP 服务器最小结构（``tool``/``resource``/``prompt`` 装饰器），供工具层类型标注。

    真实类型为 ``mcp.server.mcpserver.MCPServer``，此处以结构子类型（Protocol）代替，
    既避免对 mcp 具体类的强依赖，又让 mypy 能校验装饰器用法。
    """

    @overload
    def tool(self, name: str, **kwargs: Any) -> Callable[[_F], _F]: ...

    @overload
    def tool(self, func: _F) -> _F: ...

    def tool(self, *args: Any, **kwargs: Any) -> Any: ...

    @overload
    def resource(self, uri: str, **kwargs: Any) -> Callable[[_F], _F]: ...

    @overload
    def resource(self, func: _F) -> _F: ...

    def resource(self, *args: Any, **kwargs: Any) -> Any: ...

    @overload
    def prompt(self, name: str, **kwargs: Any) -> Callable[[_F], _F]: ...

    @overload
    def prompt(self, func: _F) -> _F: ...

    def prompt(self, *args: Any, **kwargs: Any) -> Any: ...


@dataclass
class Runtime:
    """工具调用所需的共享运行时上下文（由 ``build_server`` 注入）。"""

    config: ServerConfig
    workspace: Workspace
    transport: str = "stdio"
    logger: logging.Logger = field(default_factory=get_logger)
    _client: ITOLClient | None = field(default=None, repr=False, init=False)

    # -- 密钥 / 客户端 ---------------------------------------------------

    def client(
        self, api_key: str | None = None, *, required: bool = True
    ) -> tuple[ITOLClient, str]:
        """构建 iTOL 客户端。

        ``required=True``：密钥缺失即抛 ``APIKeyError``（上传/删除）；
        ``required=False``：导出/状态探测允许无密钥（客户端以空密钥构建）。
        """
        key: str | None
        source = ""
        try:
            key, source = resolve_api_key(
                explicit=api_key,
                key_file=self.config.effective_key_file(),
                strict_permissions=self.config.strict_permissions,
            )
        except ItolMCPError:
            if required:
                raise
            key = None
        self.logger.info(
            "iTOL 客户端初始化（密钥来源：%s，明文不落日志）", source or "未配置/显式参数"
        )
        return (
            ITOLClient(
                key,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
                backoff_factor=self.config.backoff_factor,
            ),
            source,
        )

    # -- 读取辅助 ---------------------------------------------------------

    def read_text(self, path: str | Path) -> str:
        """读取工作区内文本文件（应用配置的单文件大小上限）。"""
        return self.workspace.read_text(path, max_bytes=self.config.max_file_bytes)


def provided_pairs(values: dict[str, Any]) -> dict[str, Any]:
    """过滤出「非空」参数（None/空串/空列表/空字典视为未提供）。"""
    return {k: v for k, v in values.items() if v not in (None, "", [], {})}


def pick_one(group_name: str, values: dict[str, Any]) -> tuple[str, Any]:
    """从互斥参数组中取唯一非空者；0 个或 >1 个抛 ``UsageError``。"""
    given = provided_pairs(values)
    if len(given) == 0:
        raise UsageError(f"参数组「{'/'.join(values)}」至少需要提供一个参数（{group_name}）")
    if len(given) > 1:
        raise UsageError(f"参数 {', '.join(sorted(given))} 互斥，只能提供其一（{group_name}）")
    name, value = next(iter(given.items()))
    return name, value


def resolve_tree_text(
    runtime: Runtime,
    tree: str | None = None,
    tree_file: str | None = None,
    *,
    required: bool = True,
    group_name: str = "树",
) -> str | None:
    """将互斥对 ``tree/tree_file`` 解析为树文本。"""
    name, value = _resolve_pair(
        runtime, group_name, tree=tree, tree_file=tree_file, required=required
    )
    if value is None:
        return None
    return value if name == "tree" else runtime.read_text(value)


def resolve_table_text(
    runtime: Runtime,
    inline: str | None = None,
    table_file: str | None = None,
    *,
    required: bool = True,
    group_name: str = "表格",
) -> str | None:
    """将互斥对 ``<分组>/$file`` 解析为文本内容。"""
    name, value = _resolve_pair(
        runtime, group_name, inline=inline, table_file=table_file, required=required
    )
    if value is None:
        return None
    return value if name == "inline" else runtime.read_text(value)


def _resolve_pair(
    runtime: Runtime,
    group_name: str,
    required: bool,
    **values: Any,
) -> tuple[str, Any]:
    """泛化互斥对解析（返回 ``(参数名, 值)``）。"""
    given = provided_pairs(values)
    if len(given) == 0:
        if required:
            raise UsageError(f"参数组「{'/'.join(values)}」至少需要一个（{group_name}）")
        return "", None
    if len(given) > 1:
        raise UsageError(f"参数 {', '.join(sorted(given))} 互斥，只能提供其一（{group_name}）")
    return next(iter(given.items()))


def parse_json(value: str | None, label: str = "JSON") -> Any:
    """解析 JSON 字符串参数；非法 JSON 抛 ``UsageError``。"""
    if value is None or not str(value).strip():
        return None
    try:
        return json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise UsageError(f"{label} 不是合法 JSON：{exc}（请提供标准 JSON 字符串）") from exc


def split_commas(value: str | None) -> list[str]:
    """逗号分隔字符串 → 去空白列表。"""
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def table_to_rows(table_text: str) -> list[dict[str, Any]]:
    """表格文本 → 记录列表（NaN 转为 None，全部保留为字符串/数值原始形态）。"""
    df = parse_table_text(table_text)
    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rec: dict[str, Any] = {}
        for col in df.columns:
            val = row[col]
            if val is None or (isinstance(val, float) and val != val):  # NaN
                rec[col] = None
            else:
                rec[col] = str(val).strip()
        records.append(rec)
    return records


def preview_lines(text: str, limit: int = 40) -> str:
    """模板/文件预览：前 ``limit`` 行。"""
    lines = text.splitlines()
    if len(lines) <= limit:
        return text
    return "\n".join(lines[:limit]) + f"\n…（共 {len(lines)} 行，仅显示前 {limit} 行）"


def execute(logger: logging.Logger, name: str, fn: Any) -> dict:
    """工具函数统一执行器：受控异常 → ``ToolResult.err``；未受控异常 → 内部错误。

    保证 MCP 客户端永远收到结构化的失败结果，而非裸异常。
    """
    try:
        result = fn()
        return result.to_dict() if isinstance(result, ToolResult) else result
    except ItolMCPError as exc:
        logger.warning("工具 %s 执行失败：%s", name, exc)
        return ToolResult.err(str(exc)).to_dict()
    except Exception as exc:
        logger.exception("工具 %s 发生内部错误", name)
        return ToolResult.err(f"内部错误：{exc}").to_dict()
