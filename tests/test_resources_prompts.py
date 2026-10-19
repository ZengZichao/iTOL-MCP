"""资源与提示内容测试：3 个 help 资源、2 个引导提示的内容完整性。"""

from __future__ import annotations

from itol_mcp.tools.prompts import _PUBLICATION_GUIDE, _WORKFLOW_GUIDE
from itol_mcp.tools.resources import resource_contents


def test_template_types_resource() -> None:
    content = resource_contents()["itol://help/template-types"]
    assert content.startswith("# iTOL 模板类型速查")
    assert "DATASET_COLORSTRIP" in content
    assert "DATASET_HEATMAP" in content
    assert "itol_template_types" in content


def test_batch_api_resource() -> None:
    content = resource_contents()["itol://help/batch-api"]
    assert "# iTOL 批量接口速查" in content
    assert "batch_uploader" in content
    assert "batch_downloader" in content
    assert "SUBSCRIPTION" in content


def test_palettes_resource() -> None:
    content = resource_contents()["itol://help/palettes"]
    assert "# 配色方案速查" in content
    assert "wong" in content
    assert "okabeito" in content
    assert "ibm" in content
    assert "tol_bright" in content


def test_workflow_prompt_guide() -> None:
    assert "itol_tree_info" in _WORKFLOW_GUIDE
    assert "itol_taxonomy_monophyly" in _WORKFLOW_GUIDE
    assert "itol_upload" in _WORKFLOW_GUIDE
    assert "itol_export" in _WORKFLOW_GUIDE
    assert "常见错误规避" in _WORKFLOW_GUIDE


def test_publication_prompt_guide() -> None:
    assert "wong" in _PUBLICATION_GUIDE
    assert "okabeito" in _PUBLICATION_GUIDE
    assert "300" in _PUBLICATION_GUIDE
    assert "datasets_visible" in _PUBLICATION_GUIDE
    assert "提交前自检清单" in _PUBLICATION_GUIDE
