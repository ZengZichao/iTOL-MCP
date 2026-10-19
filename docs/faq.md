# iTOL-MCP 常见问题（FAQ）

## 上传报错如何排查？

| 报错关键词 | 含义与处理 |
|-----------|-----------|
| `ERR 0: Invalid API key` | API Key 无效：检查是否标准版订阅、三通道配置顺序是否正确 |
| `SUCCESS: 无 tree_id` | 响应无 SUCCESS 标记：检查模板格式、ZIP 内文件命名（树文件须 `*.tree`） |
| `空响应` | iTOL 返回空：检查模板规范，稍后重试 |
| `文件数超过上限` | ZIP 内文件 >50：合并或分批上传 |
| `tree_id 不存在` | 删除/导出时 ID 错误：先在 `itol_tree_info` 或项目页核对 |

## 必须订阅 iTOL 标准版吗？

- **上传**：需要 iTOL 标准版订阅 + 有效 API Key。
- **导出**：不需要订阅（但导出仍需 API Key 认证的账户）。
- **删除**：需要订阅。

## 被限流（HTTP 429）怎么办？

- 客户端会自动重试（最多 3 次、指数退避）；
- 工具描述内置「两次调用间隔数秒」提示；导出可用 `wait` 参数主动等待；
- 若持续 429：降低调用频率，或检查是否高频探测状态（`itol_query_status` 每次消耗一次导出配额）。

## 导出 PDF 为空白/过小？

- 可能树尚未渲染完成：设置 `wait`（如 `wait=10`）重试；
- 导出响应做了「最小体积」校验（如 PDF <500B 视为错误页），避免落盘空文件；
- 确认 `tree_id` 正确且树已就绪（用 `itol_query_status` 探测）。

## 如何轮换（更换）API Key？

1. 登录 iTOL 账户页（https://itol.embl.de/userInfo.cgi）生成新 Key；
2. 调用 `itol_config_set_api_key` 写入新 Key（或终端执行 `itol-mcp --set-api-key`）；
3. 旧 Key 立即失效，无需清理（日志已脱敏）。

## API Key 会泄露吗？

- 返回、日志、异常、资源内容中一律以 `***REDACTED***` 替代；
- 密钥仅用于与 `itol.embl.de` 的 HTTPS 请求，绝不随其他域名发送；
- 密钥文件权限 600，`strict_permissions` 下权限过宽直接拒绝读取；
- 请勿在对话中复述密钥；如怀疑泄露请立即轮换。

## 工作区找不到我的文件？

- 所有文件读写收束于工作区白名单（默认 `<cwd>/.itol_mcp_workspace` 或
  `$ITOL_MCP_WORKSPACE`）；
- 用 `itol_workspace_list` 查看工作区内文件；或把数据放入工作区目录再操作。

## 树文件支持哪些格式？

- Newick（`.nwk`/`.newick`/`.tree`）与 Nexus（`.nxs`/`.nexus`）；
- 上传 ZIP 内树文件须以 `.tree`/`.nwk`/`.nexus`/`.jplace` 结尾（自动归一化尾缀）。

## 模板生成报「缺少数据行」？

- `render_template` 对空数据行严格校验，需至少一行数据；
- 检查 `data_rows` / 表格 / 分类表是否为空。

## streamable-http 能暴露公网吗？

- 默认绑定 `127.0.0.1`（仅本机）；如需远程访问，请自行接入反向代理（HTTPS + 鉴权）
  与速率限制，服务端不内置公网监听。

## 更多帮助

- 工具完整参考：`docs/tools.md`
- 模板类型速查：`docs/templates.md`
- 配置说明：`docs/configuration.md`
- 安全设计：`docs/security.md`
