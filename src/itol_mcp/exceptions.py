"""异常层级。

本模块定义 iTOL-MCP 全部受控异常。工具层捕获 ``ItolMCPError`` 后统一序列化为
``ToolResult(success=False, message=...)``；未受控异常记录日志并转为「内部错误」，
保证 MCP 客户端永远接收结构化的失败结果而非裸异常。
"""


class ItolMCPError(Exception):
    """全部受控异常的基类。"""


class UsageError(ItolMCPError):
    """工具参数使用错误：互斥参数同时提供、必填缺失、取值非法等。"""


class ConfigError(ItolMCPError):
    """配置加载 / 配置文件非法。"""


class APIKeyError(ConfigError):
    """API Key 缺失 / 权限错误 / 格式非法。"""


class WorkspaceError(ItolMCPError):
    """工作区 / 路径越界或文件操作违规。"""


class TreeParseError(ItolMCPError):
    """树文件解析失败（含具体原因与疑似行号）。"""


class TaxonomyError(ItolMCPError):
    """分类学解析 / 单系群判定问题。"""


class TemplateError(ItolMCPError):
    """模板生成 / 渲染问题。"""


class TemplateTypeError(TemplateError):
    """不支持的模板类型。"""


class APIError(ItolMCPError):
    """iTOL API 传输 / 业务错误（基类）。"""


class UploadError(APIError):
    """上传失败。"""


class ExportError(APIError):
    """导出失败。"""


class DeleteError(APIError):
    """删除失败。"""
