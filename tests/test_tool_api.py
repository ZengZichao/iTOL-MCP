"""iTOL API 工具层实现测试：upload/export/upload_and_export/delete/query_status。

通过 respx 拦截 ITOLClient 的真实 HTTP，直接调用 *_impl 函数验证参数校验、
返回包装与资源清理。导出不需要订阅，上传/删除需要密钥（用 runtime fixture 的
独立密钥文件注入 api_key 显式传参）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from respx import MockResponse, MockRouter

from itol_mcp.exceptions import UsageError
from itol_mcp.tools.api_tools import (
    _delete_project_impl,
    _delete_tree_impl,
    _export_impl,
    _query_status_impl,
    _require_tree_id,
    _upload_export_impl,
    _upload_impl,
)
from itol_mcp.utils.constants import DELETE_URL, EXPORT_URL, UPLOAD_URL

API_KEY = "0123456789abcdef"


# ---------------------------------------------------------------------------
# 参数校验辅助
# ---------------------------------------------------------------------------


def test_require_tree_id_ok() -> None:
    assert _require_tree_id("  12345 ") == "12345"


def test_require_tree_id_empty() -> None:
    with pytest.raises(UsageError, match="tree_id 必填"):
        _require_tree_id("   ")


# ---------------------------------------------------------------------------
# 上传
# ---------------------------------------------------------------------------


def test_upload_impl_requires_tree(runtime) -> None:
    with pytest.raises(UsageError, match="至少需要一个"):
        _upload_impl(runtime, None, None, None, None, None, None, None, None, False, None)


def test_upload_impl_success(
    respx_mock: MockRouter, runtime, tree32_text: str
) -> None:
    runtime.workspace.write_text("data/tree.nwk", tree32_text, force=True)
    respx_mock.post(UPLOAD_URL).mock(return_value=MockResponse(200, text="SUCCESS: 777\nwarn1\nwarn2"))
    res = _upload_impl(runtime, None, "data/tree.nwk", None, None, "mytree", "desc", "proj", None, False, API_KEY)
    assert res.success is True
    assert res.data["tree_id"] == "777"
    assert res.data["project_name"] == "proj"
    assert "tree/777" in res.data["webpage"]
    assert res.warnings == ["warn1", "warn2"]


def test_upload_impl_datasets_visible_warns(
    respx_mock: MockRouter, runtime, tree32_text: str
) -> None:
    runtime.workspace.write_text("data/tree.nwk", tree32_text, force=True)
    respx_mock.post(UPLOAD_URL).mock(return_value=MockResponse(200, text="SUCCESS: 1"))
    res = _upload_impl(runtime, None, "data/tree.nwk", None, None, None, None, None, "1,2", False, API_KEY)
    assert res.success is True
    assert any("datasets_visible" in w for w in res.warnings)


def test_upload_impl_over_max_files(runtime, tree32_text: str) -> None:
    runtime.config.max_upload_files = 2
    runtime.workspace.write_text("data/tree.nwk", tree32_text, force=True)
    with pytest.raises(UsageError, match="文件数超过上限"):
        _upload_impl(runtime, None, "data/tree.nwk", ["tpl1", "tpl2"], None, None, None, None, None, False, API_KEY)


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------


def test_export_impl_requires_tree_id(runtime) -> None:
    with pytest.raises(UsageError, match="tree_id 必填"):
        _export_impl(runtime, "", "pdf", None, None, None, None, None, None, None, 0, API_KEY)


def test_export_impl_bad_display_mode(runtime) -> None:
    with pytest.raises(UsageError, match="display_mode"):
        _export_impl(runtime, "123", "pdf", None, None, None, None, 9, None, None, 0, API_KEY)


def test_export_impl_bad_dpi(runtime) -> None:
    with pytest.raises(UsageError, match="dpi"):
        _export_impl(runtime, "123", "pdf", None, 9999, None, None, None, None, None, 0, API_KEY)


def test_export_impl_success(respx_mock: MockRouter, runtime, tree32_text: str) -> None:
    payload = b"%PDF-1.4 mock " + b"x" * 600
    respx_mock.post(EXPORT_URL).mock(
        return_value=MockResponse(200, content=payload, headers={"content-type": "application/pdf"})
    )
    res = _export_impl(runtime, "123", "pdf", None, 300, None, None, 1, None, None, 0, API_KEY)
    assert res.success is True
    assert res.data["tree_id"] == "123"
    assert res.data["format"] == "pdf"
    path = Path(res.data["file"])
    assert path.is_file()
    assert path.read_bytes() == payload
    assert res.files and res.files[0]["kind"] == "image"


def test_export_impl_to_custom_output(
    respx_mock: MockRouter, runtime, tmp_path: Path, tree32_text: str
) -> None:
    payload = b"%PDF-1.4 mock " + b"x" * 600
    respx_mock.post(EXPORT_URL).mock(
        return_value=MockResponse(200, content=payload, headers={"content-type": "application/pdf"})
    )
    res = _export_impl(runtime, "123", "pdf", None, None, None, None, None, None, "out/fig.pdf", 0, API_KEY)
    assert res.success is True
    out = runtime.workspace.resolve("out/fig.pdf")
    assert out.is_file()


# ---------------------------------------------------------------------------
# 一步上传 + 导出
# ---------------------------------------------------------------------------


def test_upload_export_impl_requires_tree(runtime) -> None:
    with pytest.raises(UsageError, match="至少需要一个"):
        _upload_export_impl(runtime, None, None, None, None, "pdf", 0, None, None, None, None, None, None, None, None, None, None, False, API_KEY)


def test_upload_export_impl_success(
    respx_mock: MockRouter, runtime, tree32_text: str
) -> None:
    runtime.workspace.write_text("data/tree.nwk", tree32_text, force=True)
    respx_mock.post(UPLOAD_URL).mock(return_value=MockResponse(200, text="SUCCESS: 888\nwarn"))
    payload = b"%PDF-1.4 mock " + b"y" * 600
    respx_mock.post(EXPORT_URL).mock(
        return_value=MockResponse(200, content=payload, headers={"content-type": "application/pdf"})
    )
    res = _upload_export_impl(
        runtime, None, "data/tree.nwk", None, None, "pdf", 0, None, None, 300, None, None, None, None,
        "proj", "tn", "td", False, API_KEY,
    )
    assert res.success is True
    assert res.data["tree_id"] == "888"
    assert Path(res.data["file"]).is_file()


def test_upload_export_impl_bad_display_mode(runtime, tree32_text: str) -> None:
    runtime.workspace.write_text("data/tree.nwk", tree32_text, force=True)
    with pytest.raises(UsageError, match="display_mode"):
        _upload_export_impl(runtime, None, "data/tree.nwk", None, None, "pdf", 0, None, None, None, None, None, 9, None, None, None, None, False, API_KEY)


# ---------------------------------------------------------------------------
# 删除
# ---------------------------------------------------------------------------


def test_delete_tree_impl_success(respx_mock: MockRouter, runtime) -> None:
    respx_mock.post(DELETE_URL).mock(return_value=MockResponse(200, text="SUCCESS: deleted"))
    res = _delete_tree_impl(runtime, "123", API_KEY)
    assert res.success is True
    assert res.data["deleted"] is True


def test_delete_tree_impl_requires_id(runtime) -> None:
    with pytest.raises(UsageError, match="tree_id 必填"):
        _delete_tree_impl(runtime, "", API_KEY)


def test_delete_project_impl_success(respx_mock: MockRouter, runtime) -> None:
    respx_mock.post(DELETE_URL).mock(return_value=MockResponse(200, text="OK"))
    res = _delete_project_impl(runtime, "proj", API_KEY)
    assert res.success is True
    assert res.data["project_name"] == "proj"


def test_delete_project_impl_requires_name(runtime) -> None:
    with pytest.raises(UsageError, match="project_name 必填"):
        _delete_project_impl(runtime, "", API_KEY)


# ---------------------------------------------------------------------------
# 状态
# ---------------------------------------------------------------------------


def test_query_status_impl_ready(respx_mock: MockRouter, runtime) -> None:
    respx_mock.post(EXPORT_URL).mock(
        return_value=MockResponse(200, content=b"<svg>" + b"x" * 200, headers={"content-type": "image/svg+xml"})
    )
    res = _query_status_impl(runtime, "123", API_KEY)
    assert res.success is True
    assert res.data["status"] == "ready"


def test_query_status_impl_requires_id(runtime) -> None:
    with pytest.raises(UsageError, match="tree_id 必填"):
        _query_status_impl(runtime, "", API_KEY)
