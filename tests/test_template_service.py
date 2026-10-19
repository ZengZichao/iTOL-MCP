"""模板服务测试：注册表、渲染器 golden 断言、校验、文件输出与打包。"""

from __future__ import annotations

from pathlib import Path

import pytest

from itol_mcp.exceptions import TemplateError, TemplateTypeError
from itol_mcp.services.template_service import (
    TemplateSpec,
    create_template,
    create_templates_bundle,
    get_template_type,
    list_template_types,
    render_template,
    validate_template,
)

# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------


def test_registry_has_32_types() -> None:
    types = list_template_types()
    assert len(types) >= 32
    names = {t["type_name"] for t in types}
    for expected in (
        "color_strip",
        "heatmap",
        "simple_bar",
        "multi_bar",
        "binary",
        "gradient",
        "boxplot",
        "connections",
    ):
        assert expected in names
    assert len(names) >= 32
    assert get_template_type("color_strip").header == "DATASET_COLORSTRIP"


def test_registry_aliases() -> None:
    assert get_template_type("colorstrip").type_name == "color_strip"
    assert get_template_type("SIMPLEBAR").type_name == "simple_bar"


def test_registry_unknown_type() -> None:
    with pytest.raises(TemplateTypeError, match="不支持的模板类型"):
        get_template_type("quantum")


def test_registry_key_parameters() -> None:
    heat = next(t for t in list_template_types() if t["type_name"] == "heatmap")
    assert "FIELD_LABELS" in heat["key_parameters"]
    assert "GRADIENT" in heat["key_parameters"]


# ---------------------------------------------------------------------------
# 渲染 golden
# ---------------------------------------------------------------------------


def test_render_color_strip_golden() -> None:
    text, warnings = render_template(
        TemplateSpec(
            template_type="color_strip",
            label="MyStrip",
            data_rows=[
                {"id": "A", "value": "x", "color": "#ff0000"},
                {"id": "B", "value": "y", "color": "#00ff00"},
            ],
        )
    )
    assert text == (
        "DATASET_COLORSTRIP\n"
        "SEPARATOR TAB\n"
        "DATASET_LABEL MyStrip\n"
        "COLOR #FF0000\n"
        "DATA\n"
        "A\tx\t#FF0000\n"
        "B\ty\t#00FF00\n"
    )
    assert warnings == []


def test_render_color_strip_default_color_fills() -> None:
    text, _ = render_template(
        TemplateSpec(template_type="color_strip", label="s", data_rows=[{"id": "A", "value": "x"}])
    )
    assert "A\tx\t#FF0000" in text  # 默认色由 spec.color 回填


def test_render_heatmap_multicolumn() -> None:
    text, _ = render_template(
        TemplateSpec(
            template_type="heatmap",
            label="traits",
            data_rows=[{"id": "A", "v1": 1.5, "v2": 2.0}],
            parameters={"FIELD_LABELS": ["t1", "t2"], "WIDTH": 200},
        )
    )
    lines = text.splitlines()
    assert lines[0] == "DATASET_HEATMAP"
    assert "FIELD_LABELS t1,t2" in lines
    assert "WIDTH 200" in lines
    assert lines[-1] == "A\t1.5\t2"


def test_render_simple_bar_value_alias() -> None:
    text, _ = render_template(
        TemplateSpec(
            template_type="simple_bar", label="bar", data_rows=[{"id": "A", "value": 3.14}]
        )
    )
    assert "A\t3.14" in text


def test_render_boxplot_with_extremes() -> None:
    text, _ = render_template(
        TemplateSpec(
            template_type="boxplot",
            label="bp",
            data_rows=[
                {
                    "id": "A",
                    "minimum": 1,
                    "q1": 2,
                    "median": 3,
                    "q3": 4,
                    "maximum": 5,
                    "extreme1": 0.5,
                    "extreme2": 6,
                }
            ],
        )
    )
    assert "A\t1\t2\t3\t4\t5\t0.5\t6" in text


def test_render_tree_colors_default_type() -> None:
    text, _ = render_template(
        TemplateSpec(template_type="tree_colors", data_rows=[{"id": "A", "color": "#00ff00"}])
    )
    assert text.startswith("TREE_COLORS")
    assert "A\tlabel\t#00FF00" in text


def test_render_gradient_taxonomy_normalized(tree32_text: str) -> None:
    tax = "id,v\nA1,0\nA2,50\nA3,100\n"
    text, _ = render_template(
        TemplateSpec(
            template_type="gradient",
            label="g",
            tree=tree32_text,
            taxonomy=tax,
            column="v",
        )
    )
    data = [ln for ln in text.splitlines() if "\t" in ln]
    vals = {ln.split("\t")[0]: ln.split("\t")[1] for ln in data}
    assert vals["A1"] == "0"
    assert vals["A2"] == "0.5"
    assert vals["A3"] == "1"


def test_render_binary_taxonomy_driven(tree32_text: str) -> None:
    tax = "id,g\nA1,GX\nA2,GX\nA3,GY\n"
    text, _ = render_template(
        TemplateSpec(template_type="binary", label="b", tree=tree32_text, taxonomy=tax, column="g")
    )
    assert "A1\t1\t0" in text
    assert "A3\t0\t1" in text
    assert "FIELD_LABELS" not in text  # FIELD_LABELS 需显式传参


def test_render_unknown_parameter_warns() -> None:
    text, warnings = render_template(
        TemplateSpec(
            template_type="color_strip",
            label="s",
            data_rows=[{"id": "A", "value": "x"}],
            parameters={"BOGUS": 1},
        )
    )
    assert any("BOGUS" in w for w in warnings)
    assert "BOGUS" not in text


def test_render_invalid_color_raises() -> None:
    with pytest.raises(TemplateError, match="非法颜色"):
        render_template(
            TemplateSpec(
                template_type="color_strip",
                label="s",
                color="notacolor",
                data_rows=[{"id": "A", "value": "x"}],
            )
        )


def test_render_missing_required_rows() -> None:
    with pytest.raises(TemplateError, match="缺少数据行"):
        render_template(TemplateSpec(template_type="color_strip", label="s"))


def test_render_separator_validation() -> None:
    with pytest.raises(TemplateError, match="非法分隔符"):
        render_template(
            TemplateSpec(
                template_type="color_strip",
                separator="COLON",
                data_rows=[{"id": "A", "value": "x"}],
            )
        )


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------


GOOD_TEMPLATE = "DATASET_COLORSTRIP\nSEPARATOR TAB\nDATASET_LABEL x\nCOLOR #FF0000\nDATA\nA\ta\t#FF0000\nB\tb\t#00FF00\n"


def test_validate_good_template() -> None:
    report = validate_template(GOOD_TEMPLATE)
    assert report["valid"] is True
    assert report["header"] == "DATASET_COLORSTRIP"
    assert report["n_data_rows"] == 2


def test_validate_bad_header() -> None:
    report = validate_template("NOT_A_HEADER\nDATA\nA\tx\n")
    assert report["valid"] is False
    assert any(c["level"] == "CRITICAL" and "首行" in c["message"] for c in report["checks"])


def test_validate_missing_data_marker() -> None:
    report = validate_template("DATASET_COLORSTRIP\nSEPARATOR TAB\nA\tx\t#fff\n")
    assert report["valid"] is False
    assert any("DATA" in c["message"] for c in report["checks"])


def test_validate_inconsistent_columns() -> None:
    report = validate_template("DATASET_COLORSTRIP\nSEPARATOR TAB\nDATA\nA\tx\t#fff\nB\ty\n")
    assert any(c["level"] == "CRITICAL" and "列数不一致" in c["message"] for c in report["checks"])


def test_validate_ids_match_tree() -> None:
    report = validate_template(GOOD_TEMPLATE, tree_text="((A:1,B:1),C:1);")
    assert report["matched_ids"] == 2
    assert any(c["level"] == "PASS" and "全部" in c["message"] for c in report["checks"])


def test_validate_ids_unmatched_warns() -> None:
    report = validate_template(GOOD_TEMPLATE, tree_text="((X:1,Y:1),Z:1);")
    assert report["matched_ids"] == 0
    assert any(c["level"] == "WARN" and "匹配" in c["message"] for c in report["checks"])


def test_validate_bad_separator() -> None:
    report = validate_template("DATASET_SIMPLEBAR\nSEPARATOR PIPE\nDATA\nA\t1\n")
    assert any(c["level"] == "CRITICAL" and "非法分隔符" in c["message"] for c in report["checks"])


def test_validate_empty_template() -> None:
    report = validate_template("")
    assert report["valid"] is False


# ---------------------------------------------------------------------------
# 文件输出与打包
# ---------------------------------------------------------------------------


def test_create_template_auto_suffix(tmp_workspace) -> None:
    spec = TemplateSpec(
        template_type="color_strip", label="s", data_rows=[{"id": "A", "value": "x"}]
    )
    first = create_template(spec, tmp_workspace, out_path=None, force=False)
    assert first["template_type"] == "color_strip"
    assert (tmp_workspace.root / "templates" / "color_strip_1.txt").exists()
    create_template(
        TemplateSpec(template_type="color_strip", label="s", data_rows=[{"id": "A", "value": "x"}]),
        tmp_workspace,
        out_path=None,
    )
    assert (tmp_workspace.root / "templates" / "color_strip_2.txt").exists()


def test_create_template_exists_without_force(tmp_workspace) -> None:
    from itol_mcp.exceptions import WorkspaceError

    spec = TemplateSpec(
        template_type="color_strip", label="s", data_rows=[{"id": "A", "value": "x"}]
    )
    create_template(spec, tmp_workspace, out_path="templates/s.txt")
    with pytest.raises(WorkspaceError, match="已存在"):
        create_template(spec, tmp_workspace, out_path="templates/s.txt")


def test_create_templates_bundle(tmp_workspace) -> None:
    result = create_templates_bundle(
        [
            TemplateSpec(
                template_type="color_strip", label="a", data_rows=[{"id": "A", "value": "x"}]
            ),
            TemplateSpec(
                template_type="simple_bar", label="b", data_rows=[{"id": "A", "value": 1}]
            ),
        ],
        tmp_workspace,
        bundle_name="fig1",
    )
    assert result["n_templates"] == 2
    assert isinstance(result["files"], list) and len(result["files"]) == 2
    assert all(Path(f).is_file() for f in result["files"])
    for f in result["files"]:
        assert "/fig1/" in f
    names = [f.rsplit("/", 1)[-1] for f in result["files"]]
    assert names[0] < names[1]  # 按序号排序输出
