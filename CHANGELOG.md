# Changelog

## Unreleased

### 仓库规范

- 新增 `CONTRIBUTING.md`（贡献指南）与 `SECURITY.md`（安全政策）；
- 新增 `.github/CODEOWNERS`、`.github/dependabot.yml`、PR 模板与 Issue 模板（含私有漏洞报告入口）；
- README（中/英）补充指向贡献指南与安全政策的链接。

## 0.1.0（2026-10-19）

iTOL-MCP 首个发布版：基于 MCP（Model Context Protocol）的 iTOL 服务端，使 AI 助手可通过标准
MCP 工具完成「系统发育树检查 → 分类学与单系群分析 → iTOL 注释模板生成 → 上传 iTOL →
导出成果物」的全流程自动化。

### 新增

- **MCP 服务器装配**：33 个工具、3 个资源、2 个提示全部注册；支持 stdio（默认）与
  streamable-http（`--transport http`）双传输。
- **工作区与文件（工具 1–3）**：`itol_workspace_list` / `itol_file_read` / `itol_file_write`，
  全部文件访问收束于工作区白名单，原子写、大小限制、敏感路径拒绝。
- **树分析（工具 4–5）**：`itol_tree_info` / `itol_validate_inputs`，Newick/Nexus 检测、
  统计字段、逐项校验矩阵（PASS/WARN/CRITICAL）。
- **分类学（工具 6–8）**：`itol_taxonomy_extract` / `itol_taxonomy_monophyly` /
  `itol_taxonomy_check_and_style`，支持 GTDB/嵌入式/NCBI/auto 五种格式、单系/并系/复系
  三分类判定、LUCA/LACA/LBCA/ROOT 特殊标识符、条件美化（分支着色/高亮/色带/折叠）。
- **模板生成（工具 9–24）**：类型注册表覆盖 32 种模板类型（color_strip、heatmap、
  simple_bar、multi_bar、binary、gradient、symbols、pie_chart、externalshape、text、
  boxplot、domains、arrows、connections、tanglegram、line_chart、image、alignment、
  placement、timescale、meme、manual、labels、popup_info、tree_colors、range、style、
  collapse、prune、spacing、treestyle、my_dataset）；统一入口 + 12 个快捷入口 + 批量打包
  + 模板校验。
- **iTOL API（工具 25–30）**：`itol_upload`（ZIP 打包上传）/ `itol_export`（8 种格式 +
  参数透传）/ `itol_upload_and_export` / `itol_delete_tree` / `itol_delete_project` /
  `itol_query_status`；上传响应逐行解析、导出响应内容嗅探校验、429/5xx 指数退避重试、
  错误信息中文化映射。
- **系统（工具 31–33）**：`itol_server_info` / `itol_health_check` / `itol_config_set_api_key`。
- **安全**：API Key 三通道解析（工具参数 > 环境变量 > 密钥文件）、全程脱敏、密钥文件权限
  600、路径穿越/symlink 逃逸防护、仅 HTTPS。
- **文档与示例**：中英文 README、docs/ 五篇文档、示例数据（130 tips / 32 tips 合成树与
  配套表格）、2 个端到端脚本。测试覆盖率 ≥85%。

### 依赖

- `mcp==2.3.0`、`dendropy>=4.6,<6.0`、`pandas>=2.0,<3.0`、`PyYAML>=6.0,<7.0`、`httpx>=0.28,<1.0`、`pydantic>=2.12,<3.0`。

### 使用前提

- 上传功能需要 iTOL 标准版订阅与 API Key；导出不需要。