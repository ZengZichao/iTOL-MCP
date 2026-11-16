# 安全政策（Security Policy）

## 支持的版本

仅支持最新发布线。安全修复在 `main` 上完成，并作为当前 minor 的补丁版本发布（如 `v0.1.x`）。旧版本不接收回溯移植，请升级到最新的 `v*` tag。

| 版本 | 支持状态 |
|------|----------|
| 0.1.x | ✅ 支持 |
| < 0.1 | ❌ 不支持 |

## 报告漏洞

请使用 **GitHub 私有漏洞报告**（仓库 Security 标签页 → "Report a vulnerability"）。这能让报告、讨论与修复协调在公开发布前保持私密。

若私有报告不可用，请发送邮件至 **zengzichao@sjtu.edu.cn**，标题注明 `[iTOL-MCP security]`。**请勿**就你认为可被利用的问题公开开 issue。

预期首次响应时间为 **7 天内**。若报告被接受，修复将合入 `main`、发布补丁版本，并在发布说明中致谢（除非你要求匿名）。

## 范围（In Scope）

- **工作区文件访问**：白名单约束、路径穿越与 symlink 逃逸防护、原子写与大小限制（技术设计见 [docs/security.md](docs/security.md)）；
- **API Key 处理**：三通道解析（工具参数 > 环境变量 > 密钥文件）、日志脱敏、密钥文件权限（600）；
- **网络通信**：仅 HTTPS 与 iTOL 官方域名通信、证书校验、超时与重试策略；
- **上传/导出链路**：ZIP 打包上传与导出文件解析路径中的代码执行或资源耗尽风险；
- **工作区运行时产物**（`.itol_mcp_workspace/`）的隔离性与跨运行污染。

## 不在范围（Out of Scope）

- iTOL 官方服务端（itol.embl.de）自身的漏洞——请向 iTOL / EMBL 报告；
- 传递依赖中的漏洞——由 Dependabot 持续监控（见 `.github/dependabot.yml`）；
- 有界输入上的拒绝服务（如超大/超深树文件），除非进入内存破坏级别；
- 使用本工具上传违规数据或违反 iTOL 服务条款的行为。

## 自动化防护

- **Dependabot**：pip 依赖与 GitHub Actions 的每周安全/版本更新；
- **密钥排除**：`.itolapi.key`、`.env` 等密钥文件已在 `.gitignore` 中显式排除，仓库历史中从未包含真实密钥；
- **CI 门禁**：每次 push / PR 运行 ruff、mypy 与 pytest（覆盖率 ≥ 85%）。
