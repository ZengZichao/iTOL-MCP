# iTOL-MCP

> ⚠️ **非官方项目**：本项目为社区独立实现，与 iTOL / EMBL 官方概无关联，亦非官方发布的 MCP 服务。
> iTOL 商标与平台归其版权所有方所有；使用 iTOL 服务请遵守其[服务条款](https://itol.embl.de/help.cgi#terms)。

将 iTOL（Interactive Tree Of Life）系统发育树可视化能力封装为标准 MCP（Model Context Protocol）服务的 Python 包：AI 助手可通过 **33 个工具、3 个资源与 2 个引导提示**，完成「树检查 → 分类学/单系群分析 → iTOL 注释模板生成 → 批量上传 → 导出成果」的全流程自动化。

- 版本：0.1.0　·　Python ≥ 3.11　·　依赖 mcp==2.3.0 / dendropy / pandas / PyYAML / httpx / pydantic
- 文档：`README.md`（中文）、`README_EN.md`（English）、`docs/`（tools / templates / configuration / security / faq）

## 功能总览

| 分组 | 工具 | 能力 |
|------|------|------|
| A 工作区与文件 | 1–3 | 目录列举、文件读写（工作区白名单、原子写、大小限制） |
| B 树分析 | 4–5 | 树结构解析统计、逐项输入校验 |
| C 分类学 | 6–8 | GTDB/嵌入式/NCBI 提取、单系群检测、条件美化 |
| D 模板生成 | 9–24 | 32 种注释模板注册表、统一入口+快捷入口、批量打包、校验 |
| E iTOL API | 25–30 | ZIP 上传、8 种格式导出、一步上传导出、删除、状态探测 |
| F 系统 | 31–33 | 服务器信息、健康检查、API Key 配置 |

- **3 个资源**：`itol://help/template-types`、`itol://help/batch-api`、`itol://help/palettes`
- **2 个提示**：`itol-visualize-workflow`（可视化全流程引导）、`itol-publication-style`（出版物美化）

## 30 秒上手

```bash
# 1) 安装（python-3.11 环境）
python -m pip install -e .

# 2) 写入 iTOL API Key（只需一次）
itol-mcp --set-api-key

# 3) 注册到 MCP 客户端（示例见 docs/configuration.md）：
#    mcpServers.itol-mcp = { "command": "<python-3.11 绝对路径>/bin/itol-mcp", "args": [], "cwd": "工作目录" }

# 4) 调试
mcp dev src/itol_mcp/server.py
```

## 工作流示例

> 用户：帮我看看 `tree.nwk`，按门纲着个色带，再上传导出 300dpi 的 PDF。

LLM 调用序列：

1. `itol_tree_info(tree_file="data/tree.nwk")`
2. `itol_taxonomy_extract(tree_file="data/tree.nwk", format="auto", output="data/tax.csv")`
3. `itol_template_create_color_strip(tree_file="data/tree.nwk", taxonomy_file="data/tax.csv", column="Phylum", output="templates/strip.txt")`
4. `itol_upload_and_export(tree_file="data/tree.nwk", template_files=["templates/strip.txt"], format="pdf", dpi=300, wait=10)`
5. 汇总：tree_id、iTOL 访问链接、本地 PDF 路径。

## 快速开始（示例数据）

仓库自带合成数据（`examples/data/`：130 tips 与 32 tips 的树与配套表格），以及两个
端到端脚本：

- `examples/01_quick_figure.py`：快速出图（色带 + 热图 + 一步上传导出 PDF）；
- `examples/02_publication_style.py`：出版物美化（单系群分析 + 分支着色 + 批量模板）。

## 开发与测试

```bash
python -m pip install -e ".[dev]"
python -m pytest -q              # 单元 + Golden 测试
python -m ruff check src tests examples   # lint
python -m mypy src/itol_mcp      # 类型检查
```

测试覆盖率 ≥85%。贡献指南详见 `CONTRIBUTING.md`。

## 安全要点

- API Key 三通道（工具参数 > 环境变量 > 密钥文件），全程脱敏，密钥文件权限 600；
- 所有文件访问收束于工作区白名单，杜绝路径穿越与 symlink 逃逸；
- 仅 HTTPS 与 iTOL 官方域名通信，统一超时与重试策略；
- 详见 `docs/security.md`；发现安全漏洞请按 `SECURITY.md` 私下报告。

## 使用前提

- 上传功能需要 iTOL 标准版订阅与 API Key；导出不需要订阅；
- 数据文件须放入工作区目录或通过内联文本参数传入。

## 许可证

MIT（详见 LICENSE）。
