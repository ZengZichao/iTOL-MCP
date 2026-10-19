# iTOL-MCP 配置说明

## 配置来源与优先级

服务器按以下优先级合并配置（后者覆盖前者）：

1. **内置默认值**（见 `config.py`）；
2. **环境变量**（见下表）；
3. **配置文件** `itol_mcp.yaml`（当前目录，或 `--config` 指定路径）；
4. **命令行参数**（`--workspace`、`--transport` 等）。

## 配置文件 `config.example.yaml`

复制为 `itol_mcp.yaml` 后按需修改；未提供该文件时全部使用默认值。

| 键 | 默认值 | 说明 |
|----|--------|------|
| `workspace_dir` | `$ITOL_MCP_WORKSPACE` 或 `<cwd>/.itol_mcp_workspace` | 工作区根目录（启动自动创建） |
| `key_file` | `~/.config/itol-mcp/.itolapi.key` | 密钥文件路径 |
| `export_dir` | `<workspace>/exports` | 导出目录 |
| `template_dir` | `<workspace>/templates` | 模板输出目录 |
| `timeout` | `120.0` | 上传/导出超时（秒） |
| `max_retries` | `3` | 429/5xx 重试次数 |
| `backoff_factor` | `1.0` | 指数退避因子 |
| `max_file_bytes` | `52428800` | 单文件上限 50MB |
| `max_upload_files` | `50` | 单次上传 ZIP 内文件上限 |
| `max_rows` | `200000` | 表格行数上限 |
| `strict_permissions` | `false` | 密钥文件权限严格模式 |
| `log_level` | `INFO` | 日志级别 |

> 不要明文写入 API Key 到配置文件；密钥请走三通道（见下）。

## 环境变量

| 变量 | 说明 |
|------|------|
| `ITOL_API_KEY` | iTOL API Key（密钥通道 2） |
| `ITOL_MCP_WORKSPACE` | 自定义工作区 |
| `ITOL_MCP_LOG_LEVEL` | 日志级别 |
| `ITOL_MCP_KEY_FILE` | 密钥文件路径 |

## API Key 三通道

解析优先级：**工具参数 `api_key` > 环境变量 `ITOL_API_KEY` > 密钥文件**。

1. **工具参数**：调用上传/删除工具时显式传 `api_key`（明文仅本次调用内存中）。
2. **环境变量**：`export ITOL_API_KEY="..."`。
3. **密钥文件**：默认 `~/.config/itol-mcp/.itolapi.key`，可用工具
   `itol_config_set_api_key` 或命令 `itol-mcp --set-api-key` 写入（权限 600）。

密钥文件要求：单行 UTF-8、去首尾空白、长度 8–128、含换行/控制字符则拒绝。

## 客户端注册

### Claude Desktop（macOS）

`~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "itol-mcp": {
      "command": "<python-3.11 环境绝对路径>/bin/itol-mcp",
      "args": [],
      "cwd": "<工作目录，含树文件与工作区>"
    }
  }
}
```

### Claude Code（CLI）

```bash
claude mcp add itol-mcp --transport stdio \
  -- "<python-3.11 环境绝对路径>/bin/itol-mcp"
```

### Cursor

项目级文件 `<project>/.cursor/mcp.json`，结构同 Claude Desktop。

### CatPaw

MCP 服务器管理界面新增「本地服务器」：命令填 `<python 环境>/bin/itol-mcp`、
参数空（stdio）、工作目录含数据文件。

### streamable-http（远程/容器）

服务器侧（仅回环，不暴露公网）：

```bash
<python 环境>/bin/itol-mcp --transport http --host 127.0.0.1 --port 8731
```

客户端注册：

```json
{ "mcpServers": { "itol-mcp": { "url": "http://127.0.0.1:8731/mcp" } } }
```

> 远端部署建议经反向代理（HTTPS + 鉴权）暴露，并在代理层配置速率限制。

## 注册后连通性验证

1. `itol_server_info` → 返回版本、工作区路径、`api_key_configured`；
2. `itol_health_check` → `healthy: true`；
3. 若密钥未配置：调用 `itol_config_set_api_key`（或终端执行 `itol-mcp --set-api-key`）；
4. 试跑最小串联：`itol_tree_info` → `itol_template_create_color_strip` →
   `itol_upload_and_export`（示例数据见 `examples/data/`）。
