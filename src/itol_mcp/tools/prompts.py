"""提示（Prompts）定义：2 个引导提示（见《04 §4.9》）。

- ``itol-visualize-workflow``：端到端「核对树 → 分类学/单系群分析 → 生成模板 → 上传 → 导出」工作流引导；
- ``itol-publication-style``：出版物级可视化建议（模板组合、配色、尺寸/字体/分辨率、文件命名）。
"""

from __future__ import annotations

from itol_mcp.tools.common import MCPServerLike, Runtime

_WORKFLOW_GUIDE = """# iTOL 可视化工作流引导

请按以下步骤逐步执行，每步先确认结果再进入下一步；遇到错误按「常见错误规避」处理。

## Step 1 · 核对树
- 调用 `itol_tree_info`（tree 或 tree_file）确认：格式、末端数、分支长度、支持值、警告。
- 若无分支长度或存在重复末端名，先向用户说明并确认是否继续。

## Step 2 · （可选）分类学与单系群分析
- 树名含 GTDB/嵌入式/NCBI 分类学时：`itol_taxonomy_extract` 提取分类表；
- 需要对目标类群单系性把关时：`itol_taxonomy_monophyly`（rank 指定等级，taxa 限制目标类群）。
- 单系确认后可 `itol_taxonomy_check_and_style` 生成分支着色/高亮/色带/折叠模板。

## Step 3 · 生成注释模板
- 先 `itol_template_types` 确认目标类型的必需列与可用参数；
- 分类学驱动：`itol_template_create_color_strip`（tree_file + taxonomy_file + column，palette 选色盲友好方案）；
- 数值数据：`itol_template_create_heatmap` / `itol_template_create_simple_bar` / `itol_template_create_gradient`；
- 生成后可用 `itol_template_validate`（可选带 tree_file）校验规范与 ID 匹配度。

## Step 4 · 上传 iTOL
- `itol_upload`（tree_file + template_files）。需要：标准版订阅 + API Key。
- 密钥未配置 → 先 `itol_config_set_api_key`（或环境变量 ITOL_API_KEY / 显式 api_key 参数）。
- 上传成功返回 tree_id 与链接。

## Step 5 · 导出成果
- 上传后**间隔数秒**再导出（服务端渲染）；`itol_export` 或一步式 `itol_upload_and_export`（wait 默认 10s）。
- 位图建议 dpi=300；环形树用 display_mode=2；控制图层用 datasets_visible（如 "0,2"）。
- 清理：不再需要的树用 `itol_delete_tree` / `itol_delete_project`（不可恢复，需用户确认）。

## 常见错误规避
- **密钥缺失**：报错提示「未找到 iTOL API Key」→ 走 Step 4 的密钥配置流程；
- **ID 不匹配**：模板数据行 ID 与树末端不一致 → 先 `itol_tree_info` 核对名称，再重新生成模板；
- **渲染未就绪**：导出内容过小/空 → 增加 wait 或稍后重试；
- **限流（429/5xx）**：两次调用至少间隔数秒；避免并发批量请求；
- **订阅问题**：上传返回订阅相关错误 → 提示用户检查 iTOL 标准版订阅状态。

## 收尾
向用户汇总：tree_id、访问链接、导出文件路径，以及模板文件清单与目录结构。
""".strip()

_PUBLICATION_GUIDE = """# 出版物级可视化建议（Publication-Style）

## 模板组合（推荐）
1. **color_strip**：分类学概览（门/纲级），poly 图配色；
2. **heatmap**：连续型定量性状（基因表达、丰度、理化指标）；
3. **simple_bar / multi_bar**：单值/多值性状对比；
4. **gradient**：连续变量渐变；
5. **symbols / pie_chart**：离散特征或组成比例（少量类别时使用）；
6. 需要强调分支可信度时叠加 **tree_colors**（bootstrap 着色）。

建议顺序：色带（分类）→ 热图 → 柱状/渐变 → 连接线。数据集顺序 = 模板文件名排序。

## 配色选择（色盲友好）
- 首选 `wong` 或 `okabeito`（经色觉缺陷验证），类别 ≤8；
- `tol_bright` 适合屏幕展示（默认）；
- `tol_vibrant` 适合印刷（饱和度更高）；
- 类别 ≤5 时可选 `ibm`；
- 相同类别在多个数据集中务必使用**同一配色**（通过 `colors` 显式映射固定）。

## 尺寸 / 字体 / 分辨率
- 位图导出：**dpi=300**（期刊最低要求），大图 dpi=600；
- 画布：width/height 按期刊栏宽（单栏 ~8.8cm、双栏 ~18cm）换算像素；
- 字体：统一 Arial 或 Times New Roman，8–10pt；标签用斜体（物种名惯例）；
- 环形树（display_mode=2）适合展示 >50 tips；矩形树（1）适合带数据集图层。

## 文件命名惯例
- 模板：`templates/<type>_<n>.txt`（或自定义语义名，如 `templates/fig2_strip.txt`）；
- 导出：`exports/<tree_id>.<ext>` 或语义名：`exports/figure2_rect_300dpi.pdf`；
- 项目：`projectName` 用研究批次（如 `2026_wetland_16S`），便于 iTOL 账户管理。

## 提交前自检清单
- [ ] 树无负分支长度、无重复/空末端名；
- [ ] 模板 ID 与树 100% 匹配（`itol_template_validate` + tree_file）；
- [ ] 配色为色盲友好方案且全图一致；
- [ ] 目标类群单系性已有判断（必要时附 `itol_taxonomy_monophyly` 报告）；
- [ ] 分辨率 ≥300dpi、格式 PDF/SVG（矢量）/PNG（位图）；
- [ ] datasets_visible 图层顺序符合图注描述。
""".strip()


def register(server: MCPServerLike, runtime: Runtime) -> None:
    """向 MCP 服务器注册引导提示。"""

    @server.prompt(
        name="itol-visualize-workflow",
        title="iTOL 可视化工作流",
        description="引导 LLM 完成「核对树 → 分类学/单系群分析 → 生成模板 → 上传 → 导出」端到端流程（含常见错误规避）。",
    )
    def workflow_prompt() -> list[dict]:
        """返回工作流引导消息。"""
        return [_message("user", _WORKFLOW_GUIDE)]

    @server.prompt(
        name="itol-publication-style",
        title="出版物级可视化建议",
        description="出版物级 iTOL 可视化建议：模板组合、色盲友好配色、尺寸/字体/分辨率与文件命名。",
    )
    def publication_prompt() -> list[dict]:
        """返回出版物风格建议消息。"""
        return [_message("user", _PUBLICATION_GUIDE)]


def _message(role: str, text: str) -> dict:
    """构造 MCP PromptMessage 兼容的消息字典。"""
    return (
        {"role": role, "content": {"type": "text", "text": text}}
        if role in ("user", "assistant")
        else {}
    )
