"""`python -m itol_mcp` 入口，等价于 `itol-mcp` 命令（stdio 默认）。"""

from itol_mcp.server import run

if __name__ == "__main__":  # pragma: no cover
    run()
