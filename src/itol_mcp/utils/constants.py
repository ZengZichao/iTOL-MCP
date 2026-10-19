"""全局常量：枚举、默认值、端点 URL、路径默认值。"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 枚举（数据模型第 6.6 节）
# ---------------------------------------------------------------------------

TEMPLATE_SEPARATORS: tuple[str, ...] = ("TAB", "SPACE", "COMMA")

EXPORT_FORMATS: tuple[str, ...] = (
    "pdf",
    "svg",
    "png",
    "tiff",
    "eps",
    "newick",
    "nexus",
    "phyloxml",
)

# 位图/矢量导出格式最小体积（字节），用于导出响应二次校验
EXPORT_MIN_BYTES: dict[str, int] = {
    "pdf": 500,
    "png": 200,
    "svg": 100,
    "tiff": 200,
    "eps": 200,
    "newick": 50,
    "nexus": 100,
    "phyloxml": 100,
}

DISPLAY_MODES: dict[int, str] = {1: "矩形", 2: "环形", 3: "无根"}

TAXONOMY_FORMATS: tuple[str, ...] = ("gtdb", "embedded", "ncbi", "auto", "mixed")

MONOPHYLY_ACTIONS: tuple[str, ...] = ("color_branch", "highlight", "color_strip", "collapse")

MONOPHYLY_STATUS: tuple[str, ...] = ("mono", "para", "poly", "absent")

# 特殊宏类群标识符（细菌+古菌 MRCA 等）
TREE_META_TAXA: tuple[str, ...] = ("LUCA", "LACA", "LBCA", "ROOT")

# ---------------------------------------------------------------------------
# iTOL 批量接口端点
# ---------------------------------------------------------------------------

ITOL_BASE = "https://itol.embl.de"
UPLOAD_URL = f"{ITOL_BASE}/batch_uploader.cgi"
EXPORT_URL = f"{ITOL_BASE}/batch_downloader.cgi"
DELETE_URL = f"{ITOL_BASE}/batch_delete.cgi"

# ---------------------------------------------------------------------------
# 路径与文件默认值
# ---------------------------------------------------------------------------

DEFAULT_KEY_FILE = "~/.config/itol-mcp/.itolapi.key"
DEFAULT_WORKSPACE_NAME = ".itol_mcp_workspace"
KEY_ENV_VAR = "ITOL_API_KEY"
WORKSPACE_ENV_VAR = "ITOL_MCP_WORKSPACE"
LOG_LEVEL_ENV_VAR = "ITOL_MCP_LOG_LEVEL"
KEY_FILE_ENV_VAR = "ITOL_MCP_KEY_FILE"

# 文件扩展名 → 文件类别（workspace_list 的 kind 推断）
KIND_BY_EXT: dict[str, str] = {
    ".nwk": "tree",
    ".newick": "tree",
    ".tre": "tree",
    ".tree": "tree",
    ".nxs": "tree",
    ".nexus": "tree",
    ".nex": "tree",
    ".csv": "table",
    ".tsv": "table",
    ".tab": "table",
    ".xlsx": "table",
    ".txt": "template",
    ".dat": "template",
    ".png": "image",
    ".svg": "image",
    ".pdf": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".eps": "image",
    ".fasta": "tree",
    ".fa": "tree",
    ".faa": "tree",
    ".fna": "tree",
}

# 树文件允许扩展名（上传 ZIP 内）
TREE_EXTENSIONS: tuple[str, ...] = (".tree", ".tree.txt", ".jplace", ".nwk", ".nexus")

# 控制字符 / 双向 Unicode 检测
CONTROL_CHARS_RE = "[\x00-\x08\x0b\x0c\x0e-\x1f]"
BIDI_CHARS = {
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}

# 上传/导出等网络超时（秒）
DEFAULT_TIMEOUT = 120.0
HEALTH_CHECK_TIMEOUT = 5.0

# 重试状态码
RETRYABLE_STATUS_CODES: tuple[int, ...] = (429, 500, 502, 503, 504)

# 单节点内部标签（support value / 内节点标签）
INTERNAL_NODE_LABEL_KEY = "label"
