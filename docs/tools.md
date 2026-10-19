# iTOL-MCP 工具参考（33 个）

所有工具返回统一结构 `{success, message, data, warnings, files}`；失败时 `success=false`，
`message` 为中文可读原因，绝不返回裸异常。

> 参数说明约定：`?` 表示可选；「互斥」表示同一组参数只能提供一个，否则返回 `UsageError`。

---

## 组 A：工作区与文件（工具 1–3）

### 1. `itol_workspace_list`

列出工作区内的文件与目录。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | str? | 否 | 子路径（默认根目录） |
| `recursive` | bool? | 否 | 是否递归（默认 false） |

返回：文件列表（含路径、大小、类别 `tree/table/template/image/other`）。

### 2. `itol_file_read`

读取工作区内文本文件（上限 1MB，超过请改用工作区直连）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | str | 是 | 工作区内相对路径 |
| `start` | int? | 否 | 起始行（1 基） |
| `end` | int? | 否 | 结束行 |

### 3. `itol_file_write`

将内容写入工作区文件（自动建目录、原子写）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | str | 是 | 工作区内相对路径 |
| `content` | str | 是 | 文本内容（UTF-8） |
| `force` | bool? | 否 | 覆盖已存在文件（默认 true） |

---

## 组 B：树分析（工具 4–5）

### 4. `itol_tree_info`

解析并统计树结构信息。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tree` | str? | 互斥① | 树文本 |
| `tree_file` | str? | 互斥① | 树文件路径（工作区内） |

返回：末端数、内节点数、有根/无根、最大深度、末端标签列表、Newick/Nexus 格式识别。

### 5. `itol_validate_inputs`

对树/表格/分类表做逐项校验矩阵（每项 `PASS/WARN/CRITICAL`）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tree` / `tree_file` | str? | 互斥① | 树 |
| `table` / `table_file` | str? | 互斥② | 表格（可选） |
| `taxonomy` / `taxonomy_file` | str? | 互斥③ | 分类表（可选） |

校验项：括号平衡、控制字符/双向 Unicode、重复 tip 名、多根、表格列一致性、
分类等级完整性、颜色合法性等。

---

## 组 C：分类学（工具 6–8）

### 6. `itol_taxonomy_extract`

从树末端名称提取分类学信息（GTDB/嵌入式/NCBI/auto 五种格式）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tree` / `tree_file` | str? | 互斥① | 树 |
| `format` | str? | 否 | `gtdb/embedded/ncbi/auto/mixed`（默认 auto） |
| `output` | str? | 否 | 输出 CSV 路径（默认仅返回） |

### 7. `itol_taxonomy_monophyly`

检测类群单系性（mono/para/poly/absent 四分类）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tree` / `tree_file` | str? | 互斥① | 树 |
| `taxonomy` / `taxonomy_file` | str? | 互斥② | 分类表 |
| `group` | str | 是 | 待检类群名 |
| `rank` | str? | 否 | 等级（domain/…/genus/species） |
| `action` | str? | 否 | `color_branch/highlight/color_strip/collapse` |

### 8. `itol_taxonomy_check_and_style`

对单系类群自动生成美化模板（分支着色/高亮/色带/折叠）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tree` / `tree_file` | str? | 互斥① | 树 |
| `taxonomy` / `taxonomy_file` | str? | 互斥② | 分类表（缺省自动提取） |
| `taxon` | str | 是 | 目标类群 |
| `rank` | str? | 否 | 等级 |
| `action` | str? | 否 | 美化动作（默认 color_branch） |
| `color` | str? | 否 | 颜色（默认由配色方案自动分配） |
| `output` | str? | 否 | 模板输出路径 |

---

## 组 D：模板生成（工具 9–24）

### 9. `itol_template_types`

查询模板类型注册表（32 种）。无必填参数。

### 10. `itol_template_create`

统一模板生成入口，支持三种数据来源（内联 `data_rows` / 表格 `table|table_file` / 分类驱动 `taxonomy|taxonomy_file`）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `template_type` | str | 是 | 模板类型（见 `docs/templates.md`） |
| `label` | str? | 否 | 数据集标签（默认类型名） |
| `tree` / `tree_file` | str? | 可选 | 树（用于 ID 校验） |
| `data_rows` | list? | 可选 | 内联数据行 |
| `table` / `table_file` | str? | 可选 | 表格数据 |
| `taxonomy` / `taxonomy_file` | str? | 可选 | 分类驱动 |
| `column` | str? | 否 | 分类驱动列 |
| `parameters` | dict? | 否 | 类型参数（按白名单校验） |
| `output` | str? | 否 | 输出路径 |
| `force` | bool? | 否 | 覆盖已存在 |

### 11–22. 快捷入口（参数预绑定形态）

- `itol_template_create_color_strip`：按分类/离散列生成色带
- `itol_template_create_heatmap`：多列数值热图
- `itol_template_create_simple_bar`：单值柱状图
- `itol_template_create_multi_bar`：多值柱状图
- `itol_template_create_binary`：二元存在/缺失矩阵
- `itol_template_create_gradient`：数值渐变色带
- `itol_template_create_symbols`：符号标记
- `itol_template_create_pie_chart`：比例饼图
- `itol_template_create_connections`：连接线
- `itol_template_create_domains`：蛋白/功能域架构
- `itol_template_create_boxplot`：箱线图
- `itol_template_create_tree_ops`：树操作（collapse/prune/spacing/treestyle）

各快捷入口均含对应的核心参数，例如 `itol_template_create_color_strip` 的
`tree|tree_file`、`taxonomy|taxonomy_file`、`column`、`palette`、`color_map`、`output`。

### 23. `itol_template_bundle`

一次生成多个模板（批量打包）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `specs` | list | 是 | 规格列表（每项含 template_type/label/data_rows/parameters 等） |
| `bundle_name` | str? | 否 | 打包目录名 |
| `tree` / `tree_file` | str? | 可选 | 用于 ID 校验 |

### 24. `itol_template_validate`

校验模板文本或已生成模板的规范性。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `template` | str? | 互斥① | 模板文本 |
| `template_file` | str? | 互斥① | 模板文件路径 |

返回：头部、必需列、行数、warnings（未通过项）。

---

## 组 E：iTOL API（工具 25–30）

### 25. `itol_upload`

ZIP 打包上传树与模板到 iTOL，返回 `tree_id`。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tree` / `tree_file` | str? | 互斥① | 树 |
| `templates` / `template_files` | str? | 可选 | 模板文本 / 文件列表 |
| `project_name` | str? | 否 | 项目名（默认树文件名） |
| `tree_name` | str? | 否 | 树名 |
| `tree_description` | str? | 否 | 树描述 |
| `force` | bool? | 否 | 覆盖同名树 |
| `api_key` | str? | 否 | 显式密钥（优先级最高） |

> 需 iTOL 标准版订阅；ZIP 内文件数 ≤50。

### 26. `itol_export`

按 `tree_id` 导出成果物（8 种格式）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tree_id` | str | 是 | iTOL 树 ID |
| `format` | str? | 否 | `pdf/svg/png/tiff/eps/newick/nexus/phyloxml`（默认 pdf） |
| `datasets_visible` | str? | 否 | 数据集显隐 |
| `dpi` | int? | 否 | 位图分辨率 |
| `width` / `height` | int? | 否 | 输出尺寸 |
| `display_mode` | int? | 否 | 1 矩形/2 环形/3 无根 |
| `extra_params` | dict? | 否 | 额外透传参数 |
| `wait` | int? | 否 | 导出前等待秒数 |

返回：本地导出文件路径。

### 27. `itol_upload_and_export`

一步「上传 → 等待 → 导出」，返回 `(tree_id, 文件路径)`。参数为 `itol_upload` 与 `itol_export` 的并集。

### 28. `itol_delete_tree`

删除单棵树（不可恢复）。

### 29. `itol_delete_project`

删除整个项目（不可恢复）。

### 30. `itol_query_status`

以一次 SVG 导出探测树就绪状态（每次调用消耗一次导出配额）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tree_id` | str | 是 | iTOL 树 ID |

---

## 组 F：系统（工具 31–33）

### 31. `itol_server_info`

返回版本、环境、工作区、密钥是否已配置（仅布尔值）、导出格式、模板类型数。

### 32. `itol_health_check`

自检依赖导入、工作区可写性、iTOL 端点可达性（HEAD 5s）、密钥文件权限、模板注册表完整性。返回 `{checks, healthy}`。

### 33. `itol_config_set_api_key`

将 API Key 写入本机密钥文件（权限 600，内容不回显）。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `api_key` | str | 是 | iTOL API Key（仅本次调用内存中） |
| `key_file` | str? | 否 | 密钥文件路径（默认 `~/.config/itol-mcp/.itolapi.key`） |

---

## 对话式端到端示例

> 用户：帮我看看 tree.nwk，然后按门纲着个色带，再上传导出 300dpi 的 PDF。

LLM 工具调用序列：

1. `itol_file_write(path="data/tree.nwk", content=…)`（若内容在对话中）或 `itol_tree_info(tree_file="data/tree.nwk")`
2. `itol_taxonomy_extract(tree_file="data/tree.nwk", format="auto", output="data/tax.csv")`
3. `itol_template_create_color_strip(tree_file="data/tree.nwk", taxonomy_file="data/tax.csv", column="Phylum", output="templates/strip.txt")`
4. `itol_upload_and_export(tree_file="data/tree.nwk", template_files=["templates/strip.txt"], format="pdf", dpi=300, wait=10)`
5. 汇总：tree_id、iTOL 访问链接、本地 PDF 路径。
