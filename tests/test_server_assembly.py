"""服务器装配测试：工具/资源/提示注册完整性、命令行参数解析。"""

from __future__ import annotations

from typing import Any

from itol_mcp.server import (
    _await,
    _prompt_names,
    _resource_names,
    _set_api_key_cli,
    _tool_names,
    create_server,
    get_arg_parser,
    main,
)
from itol_mcp.tools import ALL_PROMPTS, ALL_RESOURCES, ALL_TOOLS


def _enumerate(server) -> tuple[list, list, list]:
    tools = [str(getattr(t, "name", "")) for t in _await(server.list_tools)]
    resources = [str(getattr(r, "uri", "")) for r in _await(server.list_resources)]
    prompts = [str(getattr(p, "name", "")) for p in _await(server.list_prompts)]
    return tools, resources, prompts


def test_await_works_inside_running_event_loop() -> None:
    """回归：模块级 _await 在已运行的事件循环中调用不得抛 RuntimeError。"""
    import asyncio

    async def _coro():
        return 42

    async def _inner() -> int:
        return _await(_coro)

    assert asyncio.run(_inner()) == 42


def test_await_handles_sync_and_failure() -> None:
    """同步函数走原样返回；协程抛错时向上传导。"""
    assert _await(lambda: 7) == 7

    async def _boom():
        raise ValueError("boom")

    import asyncio

    async def _inner() -> int:
        return _await(_boom)

    try:
        asyncio.run(_inner())
    except ValueError as exc:
        assert str(exc) == "boom"
    else:  # pragma: no cover
        raise AssertionError("预期 ValueError 未抛出")


def test_create_server_registers_all(tmp_path) -> None:
    from itol_mcp.config import ServerConfig

    cfg = ServerConfig(
        workspace_dir=tmp_path / "ws",
        key_file=str(tmp_path / "keys" / "k.txt"),
    )
    server = create_server(config=cfg, transport="test")
    tools, resources, prompts = _enumerate(server)
    assert set(tools) == set(ALL_TOOLS)
    assert len(tools) == 33
    assert set(resources) == set(ALL_RESOURCES)
    assert len(resources) == 3
    assert set(prompts) == set(ALL_PROMPTS)
    assert len(prompts) == 2


def test_create_server_http_transport(tmp_path) -> None:
    from itol_mcp.config import ServerConfig

    cfg = ServerConfig(workspace_dir=tmp_path / "ws")
    server = create_server(config=cfg, transport="http")
    assert len(_enumerate(server)[0]) == 33


def test_get_arg_parser_defaults() -> None:
    args = get_arg_parser().parse_args([])
    assert args.transport == "stdio"
    assert args.host == "127.0.0.1"
    assert args.port == 8731


def test_get_arg_parser_set_api_key_flag() -> None:
    args = get_arg_parser().parse_args(["--set-api-key"])
    assert args.set_api_key is True


def test_tool_names_empty_when_no_list() -> None:
    """无 list_tools 方法 → 返回空列表。"""
    class _Fake:
        pass

    assert _tool_names(_Fake()) == []


def test_resource_names_empty_when_no_list() -> None:
    class _Fake:
        pass

    assert _resource_names(_Fake()) == []


def test_prompt_names_empty_when_no_list() -> None:
    class _Fake:
        pass

    assert _prompt_names(_Fake()) == []


def test_set_api_key_cli_empty(monkeypatch, capsys) -> None:
    monkeypatch.setattr("itol_mcp.server.getpass.getpass", lambda _: "")
    assert _set_api_key_cli(None) == 1
    assert "不能为空" in capsys.readouterr().err


def test_set_api_key_cli_ok(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr("itol_mcp.server.getpass.getpass", lambda _: "0123456789abcdef")
    key_file = str(tmp_path / "k.txt")
    assert _set_api_key_cli(key_file) == 0
    assert "已写入" in capsys.readouterr().out


def test_main_set_api_key(monkeypatch) -> None:
    monkeypatch.setattr("itol_mcp.server._set_api_key_cli", lambda _: 0)
    assert main(["--set-api-key"]) == 0


def test_main_workspace_override(monkeypatch, tmp_path) -> None:
    """main 传入 --workspace 且 transport=stdio。"""
    created: list = []

    class _FakeServer:
        def run(self, *args: Any, **kwargs: Any):
            created.append(True)

    def _fake_create(config, transport="stdio"):
        return _FakeServer()

    monkeypatch.setattr("itol_mcp.server.create_server", _fake_create)
    assert main(["--workspace", str(tmp_path / "ws")]) == 0
    assert created
