# iTOL 注释模板类型速查（32 种）

> 数据源自 iTOL-MCP 的 `template_service` 注册表，与 iTOL v7 官方模板规范一致。
> 可在运行时用工具 `itol_template_types` 实时查询。

## 类型总表

| # | type_name（别名） | 头部 | 必需列 | 说明 |
|---|------------------|------|--------|------|
| 1 | `color_strip`（`colorstrip`） | `DATASET_COLORSTRIP` | id, value, color | 末端分类色带 |
| 2 | `heatmap` | `DATASET_HEATMAP` | id | 多列数值热图 |
| 3 | `simple_bar` | `DATASET_SIMPLEBAR` | id, bar_height | 单值柱状图 |
| 4 | `multi_bar` | `DATASET_MULTIBAR` | id | 多值柱状图 |
| 5 | `binary` | `DATASET_BINARY` | id | 二元存在/缺失矩阵 |
| 6 | `gradient` | `DATASET_GRADIENT` | id, value | 数值连续渐变色带 |
| 7 | `symbols`（`symbol`） | `DATASET_SYMBOL` | id, type, value, color | 符号标记 |
| 8 | `pie_chart`（`piechart`） | `DATASET_PIECHART` | id | 比例饼图 |
| 9 | `externalshape` | `DATASET_EXTERNALSHAPE` | id | 外部形状（方形/圆形/星/三角等） |
| 10 | `text` | `DATASET_TEXT` | id, text | 末端文本标注 |
| 11 | `boxplot` | `DATASET_BOXPLOT` | id, minimum, q1, median, q3, maximum | 箱线图 |
| 12 | `domains` | `DATASET_DOMAINS` | id, from, to, type | 蛋白质/功能域架构 |
| 13 | `arrows` | `DATASET_ARROWS` | id, position | 沿分支箭头 |
| 14 | `connections` | `DATASET_CONNECTION` | id1, id2 | 末端间连接线 |
| 15 | `tanglegram` | `DATASET_TANGLEGRAM` | id1, id2 | 缠结图连接 |
| 16 | `line_chart` | `DATASET_LINECHART` | id, position, value | 折线图 |
| 17 | `image` | `DATASET_IMAGE` | id, image_file | 末端图像（PNG） |
| 18 | `alignment` | `DATASET_ALIGNMENT` | id, alignment | 序列比对可视化 |
| 19 | `placement` | `DATASET_PLACEMENT` | id, position, count | 分支放置信息 |
| 20 | `timescale` | `DATASET_TIMESCALE` | time_point, label | 时间轴刻度 |
| 21 | `meme` | `DATASET_MEME` | id, start, end, name | MEME motif 架构 |
| 22 | `manual` | `DATASET_MANUAL` | （自由） | 手工/自由格式数据集 |
| 23 | `labels` | `LABELS` | id, label | 末端标签替换（注释文件） |
| 24 | `popup_info` | `POPUP_INFO` | id, title, content | 点击弹窗信息 |
| 25 | `tree_colors` | `TREE_COLORS` | id, type, color | 树枝/标签/内节点着色 |
| 26 | `range` | `DATASET_RANGE` | id, label, color | 彩色范围条 |
| 27 | `style` | `DATASET_STYLE` | id, type, color | 节点/分支样式覆盖 |
| 28 | `collapse` | `COLLAPSE` | id | 折叠子树 |
| 29 | `prune` | `PRUNE` | id | 修剪末端 |
| 30 | `spacing` | `SPACING` | id, factor | 末端行距 |
| 31 | `treestyle` | `DATASET_TREESTYLE` | id, type, style | 分支/标签样式 |
| 32 | `my_dataset` | `DATASET_MYDATASET` | id, value | 通用数据集模板 |

> 类型 23–31 中无 `DATASET_` 前缀的（`LABELS`/`POPUP_INFO`/`TREE_COLORS`/`COLLAPSE`/
> `PRUNE`/`SPACING`）为「树/标签级注释」，上传时同样作为独立文件进入 ZIP，按文件名排序决定应用顺序。

## 常用参数（`parameters` 键）

| 类型 | 常用参数（键=取值） |
|------|---------------------|
| 通用 | `DATASET_SCALE`、`LEGEND_TITLE`、`LEGEND_SHAPES`、`LEGEND_COLORS`、`LEGEND_LABELS`、`LEGEND_POSITION`（1–4） |
| color_strip | `STRIP_WIDTH`（默认 50）、`MARGIN`、`BORDER_COLOR`、`HEIGHT_FACTOR`、`COLOR_BRANCHES`（0/1） |
| heatmap | `FIELD_LABELS`、`WIDTH`、`STRIP_WIDTH`、`SHOW_STRIP_LABELS`、`INTERNAL_STRIP_WIDTH`、`BLOCKS`、`MOUSE_OVER`、`GRADIENT`、`COLOR_MIN`/`COLOR_MAX` |
| simple_bar | `MINIMUM`/`MAXIMUM`、`BAR_WIDTH`、`FILL_FRACTION`、`FILL_COLOR`、`BAR_COLOR` |
| multi_bar | `FIELD_LABELS`、`WIDTH`、`COLORS`、`HEIGHT_FACTOR`、`ALIGN_FIELDS`、`FIELD_ALIGN` |
| binary | `STRIP_WIDTH`、`COLORS`、`BORDER_COLOR`、`FIELD_LABELS` |
| gradient | `STRIP_WIDTH`、`MARGIN`、`COLOR_MIN`/`COLOR_MAX`/`COLOR_MID`、`USE_MID_COLOR` |
| symbols | `SIZE`、`SHAPE`（1 方/2 圆/3 三角/4 星）、`POSITION`、`SYMBOL_SPACING`、`COLOR` |
| pie_chart | `SIZE`、`COLORS`、`SHOW_LABELS`、`ALIGN_LABELS`、`PIE_SIZE` |
| connections | `CURVE`（0 折线/1 曲线）、`CURVATURE`、`CONNECTION_TYPE`、`LINE_WIDTH`、`COLOR`、`FORMAT` |
| domains | `STROKE_WIDTH`、`MARGIN`、`USE_MID_LINE`、`GRADIENT`、`DOMAIN_COLORS`、`DOMAIN_LABELS` |
| boxplot | `WIDTH`、`COLOR`、`EXTREME_VALUE_COLOR`、`EXTREME_SIZE`、`MINIMUM`/`MAXIMUM` |
| line_chart | `WIDTH`、`MINIMUM`/`MAXIMUM`、`GROUP_COLORS`、`GROUP_LABELS`、`SHOW_INTERNAL` |
| arrows | `HEAD_COLOR`、`BODY_COLOR`、`HEAD_SIZE`、`BODY_SIZE`、`SIZE`、`POSITION` |
| externalshape | `TYPE`（1 方/2 圆/3 星/4 右三角）、`SIZE`、`POSITION`、`SHOW_LABELS`、`SHAPE_TYPE` |
| treestyle | `STYLE`、`WIDTH`、`COLOR`（type=branch 时） |
| tree_colors | `STRIP_WIDTH`、`STRIP_COLOR`、`NODE_FORMAT`、`NODE_SHAPE__*`、`NODE_SIZE`、`NODE_COLOR` |
| timescale | `TIMESCALE_LABEL`、显示参数与树一致 |

## 配色方案（资源 `itol://help/palettes`）

| 方案 | 色值 | 适用 |
|------|------|------|
| `tol_bright` | `#4477AA #EE6677 #228833 #CCBB44 #66CCEE #AA3377 #BBBBBB` | 默认推荐 |
| `tol_vibrant` | `#EE7733 #0077BB #33BBEE #EE3377 #CC3311 #009988 #BBBBBB` | 高对比印刷 |
| `wong` | `#000000 #E69F00 #56B4E9 #009E73 #F0E442 #0072B2 #D55E00 #CC79A7` | 色盲安全 |
| `okabeito` | `#E69F00 #56B4E9 #009E73 #F0E442 #0072B2 #D55E00 #CC79A7 #000000` | 色盲安全 |
| `ibm` | `#648FFF #785EF0 #DC267F #FE6100 #FFB000` | IBM Design |

类别数超过方案色数时自动循环取色，并在 warnings 中提示。

## 模板文件通用结构

```
DATASET_COLORSTRIP                 ← 头部（第 1 行）
SEPARATOR TAB                      ← 分隔符（TAB/SPACE/COMMA）
DATASET_LABEL Phylum               ← 数据集标签
COLOR #ff0000                      ← 主色
STRIP_WIDTH 50                     ← 类型参数（按白名单）
…
DATA                               ← 数据段起始
TaxonA	#4477AA	Proteobacteria   ← 数据行
TaxonB	#EE6677	Firmicutes
```

- 无 `DATASET_` 前缀的头部同样以 `SEPARATOR` 开头并按规范渲染；
- 行尾统一 `\n`；Golden 测试锁定该格式。
