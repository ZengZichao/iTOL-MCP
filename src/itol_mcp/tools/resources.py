"""资源（Resources）定义：3 个 help 资源（见《04 §4.8》）。

- ``itol://help/template-types``：32 种模板类型速查（Markdown，机器可读版见工具 ``itol_template_types``）
- ``itol://help/batch-api``：iTOL 批量接口参数速查（上传/导出/删除）
- ``itol://help/palettes``：5 套色盲友好配色方案表

内容由注册表/常量实时构建，保证与代码一致。
"""

from __future__ import annotations

from itol_mcp.services.template_service import list_template_types
from itol_mcp.tools.common import MCPServerLike, Runtime
from itol_mcp.utils.color_tools import PALETTES

_MARKDOWN_MIME = "text/markdown"


def register(server: MCPServerLike, runtime: Runtime) -> None:
    """向 MCP 服务器注册帮助资源。"""

    @server.resource(
        "itol://help/template-types",
        name="iTOL 模板类型速查",
        description="全部 32 种受支持模板类型的速查表：类型名、头部、必需列、别名与可用参数（Markdown）。机器可读 JSON 请调用 itol_template_types 工具。",
        mime_type=_MARKDOWN_MIME,
    )
    def _res_template_types() -> str:
        return _template_types_markdown()

    @server.resource(
        "itol://help/batch-api",
        name="iTOL 批量接口速查",
        description="iTOL batch_uploader / batch_downloader / batch_delete 接口参数速查、常见错误中文映射与调用约束（Markdown）。",
        mime_type=_MARKDOWN_MIME,
    )
    def _res_batch_api() -> str:
        return _batch_api_markdown()

    @server.resource(
        "itol://help/palettes",
        name="配色方案速查",
        description="5 套色盲友好调色板（tol_bright/tol_vibrant/wong/okabeito/ibm）色值表与使用建议（Markdown）。",
        mime_type=_MARKDOWN_MIME,
    )
    def _res_palettes() -> str:
        return _palettes_markdown()


# ---------------------------------------------------------------------------
# 内容构建
# ---------------------------------------------------------------------------


def _template_types_markdown() -> str:
    lines = [
        "# iTOL 模板类型速查（32 种）",
        "",
        "> 数据行格式：id 为树末端 ID；`is_dataset=false` 的类型为树/标签级注释（无 DATA 标记）。",
        "> 机器可读 JSON 版本请调用工具 `itol_template_types`。",
        "",
        "| 类型 | 头部 | 必需列 | 说明 |",
        "|------|------|--------|------|",
    ]
    for t in sorted(list_template_types(), key=lambda x: x["type_name"]):
        aliases = ("（别名：" + ", ".join(t["aliases"]) + "）") if t["aliases"] else ""
        lines.append(
            f"| {t['type_name']}{aliases} | `{t['header']}` | {', '.join(t['required_columns']) or '（自由）'} | "
            f"{'数据集' if t['is_dataset'] else '树/标签级注释'} |"
        )
    lines += ["", "## 常用参数（parameters 白名单）", ""]
    for t in sorted(list_template_types(), key=lambda x: x["type_name"]):
        keys = t.get("key_parameters") or []
        if keys:
            lines.append(f"- **{t['type_name']}**：`{'`, `'.join(keys[:12])}`")
    lines += [
        "",
        "## 数据行示例（color_strip）",
        "",
        "```",
        "DATASET_COLORSTRIP",
        "SEPARATOR TAB",
        "DATASET_LABEL Phylum",
        "COLOR #ff0000",
        "STRIP_WIDTH 50",
        "DATA",
        "TaxonA\t#4477AA\tProteobacteria",
        "TaxonB\t#EE6677\tFirmicutes",
        "```",
        "",
    ]
    return "\n".join(lines)


def _batch_api_markdown() -> str:
    return """# iTOL 批量接口速查

> 依据 iTOL 官方 Help（https://itol.embl.de/help.cgi#batch）。

## 上传（Batch upload）— 需要标准版订阅 + API Key

- 端点：`POST https://itol.embl.de/batch_uploader.cgi`
- 文件：ZIP 打包；树文件需 `*.tree` / `*.tree.txt` / `*.jplace`；ZIP 内文件按名称排序决定数据集顺序

| 参数 | 必填 | 说明 |
|------|:---:|------|
| `zipFile` | ✅ | ZIP（multipart/form-data） |
| `APIkey` | ✅ | 账户页生成的 API Key |
| `projectName` | ✅ | 项目名（大小写敏感、账户内唯一） |
| `treeName` | 否 | 树显示名，缺省用文件名 |
| `treeDescription` | 否 | 树描述 |

响应：成功 `SUCCESS: <tree_id>`（可含警告行）；失败以 `ERR`/`ERROR`/`INVALID`/`NOT FOUND` 开头。
树访问 URL：`https://itol.embl.de/tree/<tree_id>`

### 常见错误中文映射

| 服务端特征 | 友好提示 |
|-----------|---------|
| `SUBSCRIPTION`/`REGISTRATION` | 需要有效标准版订阅 |
| `UNAUTHORIZED`/`INVALID API KEY` | API Key 无效或已轮换 |
| `FILE`/`EXTENSION`/`FORMAT` | 上传文件格式不合法 |
| `NOT FOUND` | 指定对象不存在 |
| `SIZE`/`LARGE` | 文件过大 |
| `BUSY`/`TIMEOUT` | 服务器繁忙，稍后重试 |

## 导出（Batch export）— 无需订阅

- 端点：`POST https://itol.embl.de/batch_downloader.cgi`
- 必填：`tree`（数字树 ID）、`format`（pdf/svg/png/tiff/eps/newick/nexus/phyloxml）

常用参数（可用 `extra_params` 透传）：

| 参数 | 取值/说明 |
|------|-----------|
| `datasets_visible` | 逗号分隔数据集索引（0 起，如 `0,2,5`） |
| `display_mode` | 1 矩形 / 2 环形 / 3 无根 |
| `dpi` / `width` / `height` | 位图分辨率 / 画布尺寸（像素） |
| `current_font_size`/`current_font_name`/`current_font_style` | 标签字体 |
| `label_display` / `align_labels` / `dashed_lines` | 标签显示控制 |
| `ignore_branch_length` | 0/1 忽略分支长度 |
| `leaf_sorting` | 1 正常 / 2 不排序 |
| `arc` / `rotation` | 环形显示弧角 / 旋转 |
| `line_width` / `default_branch_color` / `default_label_color` | 线宽与默认颜色 |
| `bootstrap_display` 及 `bootstrap_*` | 引导值显示全套参数 |
| `newick_format` | `ID`：Newick 内含内部节点 ID |

响应校验：HTML 错误页 / 短文本错误 / 小于格式最小体积（pdf 500B、png 200B、svg 100B、tiff 200B、eps 200B）均视为失败。

## 删除（Batch delete）— 需要订阅，不可恢复

- 端点：`POST https://itol.embl.de/batch_delete.cgi`
- 参数：`tree`（树 ID，删单树）或 `project`（项目名，删整个项目；大小写敏感）
- 成功判定：响应含 `SUCCESS`/`OK`/`DONE`

## 调用约束

1. 仅 HTTPS；2. 批量操作间隔建议 ≥ 数秒（尤其 PNG 导出）；3. 上传/导出有 429/5xx 指数退避重试；4. 树 ID 为数字字符串。
"""


def _palettes_markdown() -> str:
    lines = [
        "# 配色方案速查（色盲友好）",
        "",
        "> 适用：color_strip / heatmap / symbols / multi_bar 等模板的自动取色与出版物配色建议。",
        "> 类别数超过方案色数时自动循环取色并给出 WARNING。",
        "",
        "| 方案 | 色值 | 适用 |",
        "|------|------|------|",
    ]
    notes = {
        "tol_bright": "默认推荐",
        "tol_vibrant": "高对比印刷",
        "wong": "色盲安全（Wong 2011）",
        "okabeito": "色盲安全（Okabe & Ito 2008）",
        "ibm": "IBM Design",
    }
    for name, colors in PALETTES.items():
        hexes = " ".join(colors)
        lines.append(f"| `{name}` | `{hexes}` | {notes.get(name, '')} |")
    lines += [
        "",
        "## 使用建议",
        "- 科研图表优先 `wong` / `okabeito`（经过色觉缺陷验证）；",
        "- 需要印刷对比度时用 `tol_vibrant`；",
        "- 类别 ≤5 时 `ibm` 五色足够；",
        '- 也可通过 `colors` 参数提供自定义 `{"类别":"#RRGGBB"}` 映射覆盖取色。',
        "",
    ]
    return "\n".join(lines)


def resource_contents() -> dict[str, str]:
    """供测试使用的资源内容映射。"""
    return {
        "itol://help/template-types": _template_types_markdown(),
        "itol://help/batch-api": _batch_api_markdown(),
        "itol://help/palettes": _palettes_markdown(),
    }
