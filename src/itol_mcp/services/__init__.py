"""服务层：领域逻辑，与 MCP 解耦（不 import 任何 MCP 相关模块，可直接单测）。

- ``workspace_service``：工作区白名单文件访问
- ``tree_service``：树解析与统计、输入校验
- ``taxonomy_service``：分类学解析与单系群判定
- ``template_service``：模板注册表 + 渲染器
- ``api_service``：iTOL 批量接口客户端
"""

from itol_mcp.services.api_service import ITOLClient
from itol_mcp.services.taxonomy_service import (
    check_and_style,
    check_monophyly,
    extract_taxonomy_from_names,
)
from itol_mcp.services.template_service import (
    TemplateSpec,
    create_template,
    create_templates_bundle,
)
from itol_mcp.services.tree_service import summarize, validate_batch
from itol_mcp.services.workspace_service import Workspace

__all__ = [
    "ITOLClient",
    "TemplateSpec",
    "Workspace",
    "check_and_style",
    "check_monophyly",
    "create_template",
    "create_templates_bundle",
    "extract_taxonomy_from_names",
    "summarize",
    "validate_batch",
]
