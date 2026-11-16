# 参与贡献（Contributing to iTOL-MCP）

感谢你对 iTOL-MCP 的关注！本文档说明参与贡献的方式、开发环境配置与项目规范。

## 目录

- [行为准则](#行为准则)
- [快速开始](#快速开始)
- [开发环境](#开发环境)
- [代码风格](#代码风格)
- [测试](#测试)
- [提交与 PR 流程](#提交与-pr-流程)
- [报告问题](#报告问题)
- [许可证](#许可证)
- [联系方式](#联系方式)

## 行为准则

请保持友善、尊重与专业的交流。我们重视每一位贡献者，任何骚扰、歧视或人身攻击都不被容忍。

## 快速开始

### 前置条件

- Python ≥ 3.11（CI 覆盖 3.11 / 3.12 / 3.13）
- Git
- 基本了解系统发育树（Newick / Nexus）与 MCP 协议者更佳

### Fork 与克隆

1. 在 GitHub 上 Fork 本仓库
2. 克隆你的 Fork：
   ```bash
   git clone https://github.com/your-username/iTOL-MCP.git
   cd iTOL-MCP
   ```
3. 添加上游仓库：
   ```bash
   git remote add upstream https://github.com/ZengZichao/iTOL-MCP.git
   ```

## 开发环境

```bash
# 创建并激活虚拟环境（任选其一）
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 安装开发依赖（可编辑模式）
pip install -e ".[dev]"
```

## 代码风格

项目使用 [ruff](https://docs.astral.sh/ruff/) 统一 lint 与 import 排序，使用 mypy（strict）做类型检查：

- 行宽 100，目标 Python 3.11；
- 规则集：`E, F, W, I, B, C4, S, UP, RUF, SIM, ANN`（见 `pyproject.toml`，含少量有注释说明的豁免）；
- 公共函数需带类型标注与文档字符串（中文 docstring 为本项目惯例）；
- MCP 工具返回统一结构 `{success, message, data, warnings, files}`。

```bash
python -m ruff check src tests examples
python -m mypy src/itol_mcp
```

## 测试

```bash
python -m pytest -q                                # 全部测试
python -m pytest -q -m "not integration"           # 跳过真实 iTOL API 集成测试
python -m coverage run -m pytest -q                # 带覆盖率
python -m coverage report --fail-under=85          # 覆盖率门槛 85%
```

- 新增功能请同步新增测试；`tests/` 下按被测模块命名；
- 标记 `integration` 的测试需要真实 `ITOL_API_KEY`，默认跳过，请勿在 CI 外泄露密钥；
- 覆盖率低于 85% 时 CI 会失败。

## 提交与 PR 流程

1. **同步上游**：
   ```bash
   git fetch upstream
   git merge upstream/main
   ```
2. **新建特性分支**：`git checkout -b feature/your-feature-name`
3. **开发与自测**：完成代码、测试与文档更新，跑通 ruff / mypy / pytest
4. **更新 CHANGELOG.md**（`Unreleased` 段落）
5. **提交**（信息建议遵循 `feat:` / `fix:` / `docs:` / `chore:` 前缀）
6. **推送并创建 PR**：PR 模板已提供检查清单，请逐项确认
7. **合并**：CI 全绿、自查 diff 无误后合并（单一维护者项目，无需第二评审人）

## 报告问题

- **Bug**：使用 [Bug Report 模板](https://github.com/ZengZichao/iTOL-MCP/issues/new?template=bug_report.md)，请附复现步骤、环境与完整错误输出；
- **功能建议**：使用 [Feature Request 模板](https://github.com/ZengZichao/iTOL-MCP/issues/new?template=feature_request.md)；
- **安全漏洞**：请**不要**开公开 issue，按 [SECURITY.md](SECURITY.md) 私下报告。

## 许可证

向 iTOL-MCP 贡献即表示你同意你的贡献以 [MIT License](LICENSE) 发布。

## 联系方式

- 邮箱：zengzichao@sjtu.edu.cn
- Issues：https://github.com/ZengZichao/iTOL-MCP/issues

感谢你的贡献！
