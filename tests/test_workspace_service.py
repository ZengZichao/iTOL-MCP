"""工作区服务测试：路径边界、原子写、文件名消毒、目录列举。"""

from __future__ import annotations

from pathlib import Path

import pytest

from itol_mcp.exceptions import WorkspaceError
from itol_mcp.services.workspace_service import Workspace


def test_resolve_relative_inside_root(tmp_workspace: Workspace) -> None:
    got = tmp_workspace.resolve("data/a.nwk")
    assert got == (tmp_workspace.root / "data" / "a.nwk").resolve()


def test_resolve_absolute_inside_root(tmp_workspace: Workspace) -> None:
    target = tmp_workspace.root / "templates" / "x.txt"
    target.write_text("x", encoding="utf-8")
    assert tmp_workspace.resolve(str(target)) == target.resolve()


def test_resolve_escape_blocked(tmp_workspace: Workspace) -> None:
    with pytest.raises(WorkspaceError, match="越界"):
        tmp_workspace.resolve("../outside.txt")


def test_write_and_read_roundtrip(tmp_workspace: Workspace) -> None:
    path = tmp_workspace.write_text("data/t.csv", "a,b\n1,2\n")
    assert path.read_text(encoding="utf-8") == "a,b\n1,2\n"
    assert tmp_workspace.read_text("data/t.csv") == "a,b\n1,2\n"


def test_write_existing_rejects_without_force(tmp_workspace: Workspace) -> None:
    tmp_workspace.write_text("templates/t.txt", "v1")
    with pytest.raises(WorkspaceError, match="已存在"):
        tmp_workspace.write_text("templates/t.txt", "v2")
    assert tmp_workspace.read_text("templates/t.txt") == "v1"
    tmp_workspace.write_text("templates/t.txt", "v2", force=True)
    assert tmp_workspace.read_text("templates/t.txt") == "v2"


@pytest.mark.parametrize(
    "name",
    [".hidden", ".itolapi.key", "a/../b", "/abs/path", "~home", "dir/.git/config", "x\x00y"],
)
def test_path_for_rejects_unsafe(tmp_workspace: Workspace, name: str) -> None:
    with pytest.raises(WorkspaceError):
        tmp_workspace.path_for(name)


def test_path_for_allows_nested_relative(tmp_workspace: Workspace) -> None:
    got = tmp_workspace.path_for("templates/strip.txt")
    assert got == (tmp_workspace.root / "templates" / "strip.txt").resolve()


def test_write_forbidden_keyfile_name(tmp_workspace: Workspace) -> None:
    with pytest.raises(WorkspaceError, match="禁止写入"):
        tmp_workspace.write_text(".itolapi.key", "secret")


def test_list_kinds_by_extension(tmp_workspace: Workspace) -> None:
    tmp_workspace.write_text("data/t.nwk", "((A,B),C);")
    tmp_workspace.write_text("data/t.csv", "id,v\nA,1\n")
    tmp_workspace.write_text("templates/s.txt", "DATASET_COLORSTRIP")
    tmp_workspace.write_text("data/img.png", "notapng")
    entries = {e["name"]: e["kind"] for e in tmp_workspace.list("data")}
    assert entries["t.nwk"] == "tree"
    assert entries["t.csv"] == "table"
    assert entries["img.png"] == "image"
    types = {e["name"]: e["kind"] for e in tmp_workspace.list()}
    assert types["templates"] == "dir"


def test_read_missing_file(tmp_workspace: Workspace) -> None:
    with pytest.raises(WorkspaceError, match="不存在"):
        tmp_workspace.read_text("nope.txt")


def test_read_max_bytes(tmp_workspace: Workspace) -> None:
    tmp_workspace.write_text("data/big.txt", "x" * 100)
    with pytest.raises(WorkspaceError, match="过大"):
        tmp_workspace.read_text("data/big.txt", max_bytes=10)


def test_init_creates_subdirs(tmp_path: Path) -> None:
    ws = Workspace(tmp_path / "ws")
    for sub in ("templates", "exports", "data", "logs"):
        assert (ws.root / sub).is_dir()
