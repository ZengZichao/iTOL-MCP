"""pytest 共享夹具：示例数据、临时工作区与运行时上下文。"""

from __future__ import annotations

from pathlib import Path

import pytest

from itol_mcp.config import ServerConfig
from itol_mcp.services.workspace_service import Workspace
from itol_mcp.tools.common import Runtime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DATA = PROJECT_ROOT / "examples" / "data"


def _read(name: str) -> str:
    return (EXAMPLES_DATA / name).read_text(encoding="utf-8")


@pytest.fixture
def tree32_text() -> str:
    """32 末端演示树（含 mono/para/poly 演示类群）。"""
    return _read("synthetic_32tips.nwk")


@pytest.fixture
def tax32_text() -> str:
    """32 末端分类表（全名列 Domain/…/Genus）。"""
    return _read("synthetic_32tips_taxonomy.csv")


@pytest.fixture
def tree130_text() -> str:
    """130 末端随机合并树（嵌入式 GTDB 风格名称）。"""
    return _read("synthetic_130tips.nwk")


@pytest.fixture
def tax130_text() -> str:
    """130 末端分类表（短名列 d/p/c/o/f/g/s）。"""
    return _read("synthetic_130tips_taxonomy.csv")


@pytest.fixture
def traits130_text() -> str:
    """130 末端数值性状表。"""
    return _read("synthetic_130tips_traits.csv")


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Workspace:
    """临时工作区（自动创建 templates/exports/data/logs 子目录）。"""
    return Workspace(tmp_path / "workspace")


@pytest.fixture
def runtime(tmp_path: Path, tmp_workspace: Workspace) -> Runtime:
    """带临时工作区与独立密钥文件的运行时（避免触碰真实家目录密钥）。"""
    cfg = ServerConfig(
        workspace_dir=tmp_workspace.root,
        key_file=str(tmp_path / "keys" / ".itolapi.key"),
        strict_permissions=False,
    )
    return Runtime(config=cfg, workspace=tmp_workspace)


SMALL_TREE = "((A:0.1,B:0.2):0.3,C:0.4);"
SMALL_TAXONOMY = "id,d,p\nA,Bacteria,Firmicutes\nB,Bacteria,Firmicutes\nC,Bacteria,Proteobacteria\n"
