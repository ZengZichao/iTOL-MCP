"""一次性冒烟脚本：构建服务器并枚举工具/资源/提示。"""
import sys
import tempfile
from pathlib import Path

from itol_mcp import build_server
from itol_mcp.config import ServerConfig
from itol_mcp.server import _prompt_names, _resource_names, _tool_names

ws = Path(tempfile.mkdtemp())
srv = build_server(ServerConfig(workspace_dir=ws))
tools = _tool_names(srv)
res = _resource_names(srv)
pr = _prompt_names(srv)
print("tools:", len(tools))
print("resources:", len(res))
print("prompts:", len(pr))
print("sample tools:", tools[:6], "...", tools[-3:])
missing = [
    n
    for n in (
        "itol_workspace_list",
        "itol_tree_info",
        "itol_taxonomy_monophyly",
        "itol_template_create_color_strip",
        "itol_upload",
        "itol_config_set_api_key",
    )
    if n not in tools
]
print("missing:", missing)
sys.exit(1 if (missing or len(tools) != 33 or len(res) != 3 or len(pr) != 2) else 0)