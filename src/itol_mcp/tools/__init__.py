"""工具层：33 个工具 + 3 个资源 + 2 个提示的注册聚合。

``register_all(server, runtime)`` 由 ``server.build_server`` 调用，完成全部注册。
"""

from __future__ import annotations

from itol_mcp.tools.common import MCPServerLike, Runtime, execute  # noqa: F401 —— 供测试直接引用

# 全部工具名（与《04 §4.10》矩阵一致，顺序即分组顺序）
ALL_TOOLS: tuple[str, ...] = (
    # A 工作区与文件
    "itol_workspace_list",
    "itol_file_read",
    "itol_file_write",
    # B 树分析
    "itol_tree_info",
    "itol_validate_inputs",
    # C 分类学
    "itol_taxonomy_extract",
    "itol_taxonomy_monophyly",
    "itol_taxonomy_check_and_style",
    # D 模板生成
    "itol_template_types",
    "itol_template_create",
    "itol_template_create_color_strip",
    "itol_template_create_heatmap",
    "itol_template_create_simple_bar",
    "itol_template_create_multi_bar",
    "itol_template_create_binary",
    "itol_template_create_gradient",
    "itol_template_create_symbols",
    "itol_template_create_pie_chart",
    "itol_template_create_connections",
    "itol_template_create_domains",
    "itol_template_create_boxplot",
    "itol_template_create_tree_ops",
    "itol_template_bundle",
    "itol_template_validate",
    # E iTOL API
    "itol_upload",
    "itol_export",
    "itol_upload_and_export",
    "itol_delete_tree",
    "itol_delete_project",
    "itol_query_status",
    # F 系统
    "itol_server_info",
    "itol_health_check",
    "itol_config_set_api_key",
)

ALL_RESOURCES: tuple[str, ...] = (
    "itol://help/template-types",
    "itol://help/batch-api",
    "itol://help/palettes",
)

ALL_PROMPTS: tuple[str, ...] = (
    "itol-visualize-workflow",
    "itol-publication-style",
)


def register_all(server: MCPServerLike, runtime: Runtime) -> None:
    """注册全部 33 工具 + 3 资源 + 2 提示。"""
    from itol_mcp.tools import (
        api_tools,
        prompts,
        resources,
        system_tools,
        taxonomy_tools,
        template_tools,
        tree_tools,
        workspace_tools,
    )

    for module in (
        workspace_tools,
        tree_tools,
        taxonomy_tools,
        template_tools,
        api_tools,
        system_tools,
    ):
        module.register(server, runtime)
    resources.register(server, runtime)
    prompts.register(server, runtime)
