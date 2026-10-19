"""iTOL API 服务测试：上传/导出/删除/状态（respx mock HTTP）。

网络请求全部由 respx 拦截，不触达真实 iTOL。每个测试通过 ``respx_mock``
fixture（respx 0.23 注入的 MockRouter）注册匹配路由，确保隔离。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from respx import MockResponse, MockRouter

from itol_mcp.exceptions import DeleteError, ExportError, UploadError
from itol_mcp.services.api_service import ITOLClient, _tree_arcname
from itol_mcp.utils.constants import DELETE_URL, EXPORT_URL, UPLOAD_URL

API_KEY = "0123456789abcdef"


@pytest.fixture
def client() -> ITOLClient:
    return ITOLClient(api_key=API_KEY, max_retries=0, timeout=10)


@pytest.fixture
def tree_file(tmp_path: Path) -> Path:
    f = tmp_path / "tree.tree"
    f.write_text("((A,B),C);", encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# 上传
# ---------------------------------------------------------------------------


def test_upload_success(respx_mock: MockRouter, client: ITOLClient, tree_file: Path) -> None:
    respx_mock.post(UPLOAD_URL).mock(
        return_value=MockResponse(200, text="SUCCESS: 12345\nWarning line")
    )
    tree_id, warnings = client.upload(tree_file, template_files=[])
    assert tree_id == "12345"
    assert warnings == ["Warning line"]


def test_upload_requires_key(tree_file: Path) -> None:
    client = ITOLClient(api_key=None, max_retries=0)
    with pytest.raises(UploadError, match="API Key"):
        client.upload(tree_file)


def test_upload_error_response(respx_mock: MockRouter, client: ITOLClient, tree_file: Path) -> None:
    respx_mock.post(UPLOAD_URL).mock(return_value=MockResponse(200, text="ERR: INVALID API KEY"))
    with pytest.raises(UploadError, match="API Key 无效"):
        client.upload(tree_file)


def test_upload_empty_response(respx_mock: MockRouter, client: ITOLClient, tree_file: Path) -> None:
    respx_mock.post(UPLOAD_URL).mock(return_value=MockResponse(200, text=""))
    with pytest.raises(UploadError, match="空响应"):
        client.upload(tree_file)


def test_upload_no_success_marker(
    respx_mock: MockRouter, client: ITOLClient, tree_file: Path
) -> None:
    respx_mock.post(UPLOAD_URL).mock(return_value=MockResponse(200, text="just some text"))
    with pytest.raises(UploadError, match="SUCCESS"):
        client.upload(tree_file)


def test_upload_zip_arcname_conventions(client: ITOLClient, tree_file: Path) -> None:
    assert _tree_arcname(Path("a.tree")) == "a.tree"
    assert _tree_arcname(Path("a.tree.txt")) == "a.tree"
    assert _tree_arcname(Path("a.nwk.txt")) == "a.nwk"
    assert _tree_arcname(Path("plain.txt")) == "plain.txt.tree"


def test_upload_too_many_files(client: ITOLClient, tree_file: Path) -> None:
    many = [tree_file] * 60
    with pytest.raises(UploadError, match="上限"):
        client.upload(tree_file, template_files=many)


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------


def test_export_success(respx_mock: MockRouter, client: ITOLClient, tmp_path: Path) -> None:
    payload = b"%PDF-1.4 mock pdf content " + b"x" * 600
    respx_mock.post(EXPORT_URL).mock(
        return_value=MockResponse(200, content=payload, headers={"content-type": "application/pdf"})
    )
    out = client.export("12345", fmt="pdf", out_dir=tmp_path)
    assert out.is_file()
    assert out.name == "12345.pdf"
    assert out.read_bytes() == payload


def test_export_html_error_page(respx_mock: MockRouter, client: ITOLClient, tmp_path: Path) -> None:
    respx_mock.post(EXPORT_URL).mock(
        return_value=MockResponse(
            200, content=b"<html><title>Error</title></html>", headers={"content-type": "text/html"}
        )
    )
    with pytest.raises(ExportError, match="错误页"):
        client.export("12345", fmt="pdf", out_dir=tmp_path)


def test_export_bad_format(respx_mock: MockRouter, client: ITOLClient, tmp_path: Path) -> None:
    with pytest.raises(ExportError, match="不支持的导出格式"):
        client.export("12345", fmt="gif", out_dir=tmp_path)


def test_export_too_small(respx_mock: MockRouter, client: ITOLClient, tmp_path: Path) -> None:
    respx_mock.post(EXPORT_URL).mock(
        return_value=MockResponse(200, content=b"tiny", headers={"content-type": "application/pdf"})
    )
    with pytest.raises(ExportError, match="过小"):
        client.export("12345", fmt="pdf", out_dir=tmp_path)


def test_export_short_error_text(
    respx_mock: MockRouter, client: ITOLClient, tmp_path: Path
) -> None:
    respx_mock.post(EXPORT_URL).mock(
        return_value=MockResponse(
            200, content=b"Error: not found", headers={"content-type": "text/plain"}
        )
    )
    with pytest.raises(ExportError, match="导出失败"):
        client.export("12345", fmt="pdf", out_dir=tmp_path)


def test_export_retry_on_429_then_success(
    respx_mock: MockRouter, client: ITOLClient, tmp_path: Path
) -> None:
    client.max_retries = 2
    client.backoff_factor = 0.0
    route = respx_mock.post(EXPORT_URL).mock(
        side_effect=[
            MockResponse(429),
            MockResponse(200, content=b"x" * 600, headers={"content-type": "application/pdf"}),
        ]
    )
    out = client.export("12345", fmt="pdf", out_dir=tmp_path)
    assert out.is_file()
    assert len(route.calls) == 2


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------


def test_delete_tree_success(respx_mock: MockRouter, client: ITOLClient) -> None:
    respx_mock.post(DELETE_URL).mock(return_value=MockResponse(200, text="SUCCESS: deleted"))
    ok, msg = client.delete_tree("12345")
    assert ok is True
    assert "SUCCESS" in msg


def test_delete_project_success(respx_mock: MockRouter, client: ITOLClient) -> None:
    respx_mock.post(DELETE_URL).mock(return_value=MockResponse(200, text="OK"))
    ok, _ = client.delete_project("myproj")
    assert ok is True


def test_delete_error(respx_mock: MockRouter, client: ITOLClient) -> None:
    respx_mock.post(DELETE_URL).mock(return_value=MockResponse(200, text="ERR: NOT FOUND"))
    with pytest.raises(DeleteError, match="不存在"):
        client.delete_tree("999")


def test_delete_requires_key() -> None:
    client = ITOLClient(api_key=None)
    with pytest.raises(DeleteError, match="API Key"):
        client.delete_tree("12345")


# ---------------------------------------------------------------------------
# 状态
# ---------------------------------------------------------------------------


def test_query_status_ready(respx_mock: MockRouter, client: ITOLClient) -> None:
    respx_mock.post(EXPORT_URL).mock(
        return_value=MockResponse(
            200, content=b"<svg>" + b"x" * 200, headers={"content-type": "image/svg+xml"}
        )
    )
    status = client.query_status("12345")
    assert status["status"] == "ready"
    assert status["ready"] is True


def test_query_status_unknown_on_error(respx_mock: MockRouter, client: ITOLClient) -> None:
    respx_mock.post(EXPORT_URL).mock(
        return_value=MockResponse(200, content=b"tiny", headers={"content-type": "image/svg+xml"})
    )
    status = client.query_status("12345")
    assert status["status"] == "unknown"
    assert status["ready"] is False
