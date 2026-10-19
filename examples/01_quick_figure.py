#!/usr/bin/env python
"""端到端示例 01：快速出图 —— 树统计 + 单系性检查 + 条件美化 + 分类学驱动模板。

完全离线运行（不调用 iTOL 网络 API），使用 ``examples/data/synthetic_32tips.*``：

1. 解析 32 末端演示树并输出统计信息；
2. 基于「树 + 分类表」对全部 Genus 做单系性检查（mono / para / poly）；
3. 对单系类群 GenusA 生成分支着色模板（TREE_COLORS）；
4. 演示并系类群 GenusD：默认跳过并注明原因，strict=true 时抛错保护；
5. 演示复系类群 GenusE：同样被跳过；
6. 分类学驱动生成 color_strip（按 Phylum）与 binary（按 Genus）模板；
7. 对全部生成模板做 iTOL 规范校验（含 ID 与树匹配度检查）。

运行（在项目根目录）：
    python examples/01_quick_figure.py
输出目录：
    examples/output/01_quick_figure/
"""

from __future__ import annotations

import sys
from pathlib import Path

from itol_mcp.exceptions import TaxonomyError
from itol_mcp.services.taxonomy_service import (
    check_and_style,
    check_monophyly,
    summarize_monophyly,
)
from itol_mcp.services.template_service import (
    TemplateSpec,
    create_template,
    validate_template,
)
from itol_mcp.services.tree_service import summarize
from itol_mcp.services.workspace_service import Workspace

# 项目根目录定位（兼容从任意工作目录启动）
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "examples" / "data"
OUT = ROOT / "examples" / "output" / "01_quick_figure"

TREE_FILE = DATA / "synthetic_32tips.nwk"
TAXONOMY_FILE = DATA / "synthetic_32tips_taxonomy.csv"


def header(title: str) -> None:
    print("\n" + "=" * 64)
    print(" " + title)
    print("=" * 64)


def main() -> None:
    tree_text = TREE_FILE.read_text(encoding="utf-8")
    tax_text = TAXONOMY_FILE.read_text(encoding="utf-8")
    workspace = Workspace(OUT)
    generated: list[Path] = []

    # 1) 树统计 ------------------------------------------------------------
    header("1) 树统计信息（synthetic_32tips.nwk）")
    info = summarize(tree_text)
    print(f"  格式：{info.format}；末端 {info.n_tips}；内部节点 {info.n_internal}")
    print(
        f"  分支长度：{'有' if info.has_branch_lengths else '无'}；"
        f"最大深度 {info.max_depth}；总长 {info.total_branch_length}"
    )
    for w in info.warnings:
        print(f"  [警告] {w}")
    print("  末端预览：", ", ".join(info.tips[:6]), "…")

    # 2) 单系性检查 ----------------------------------------------------------
    header("2) 单系性检查（rank=Genus，全部类群）")
    results = check_monophyly(tree_text, tax_text, rank="Genus")
    by_status: dict[str, list[str]] = {"mono": [], "para": [], "poly": [], "absent": []}
    for r in results:
        by_status[r["status"]].append(f"{r['group']}({r['member_count']})")
    for status, groups in by_status.items():
        if groups:
            print(f"  {status:>6}：{', '.join(groups)}")
    print("  汇总：", summarize_monophyly(results))

    # 3) 单系类群条件美化 ------------------------------------------------------
    header("3) 单系类群 GenusA → 分支着色（color_branch）")
    styled = check_and_style(
        tree_text, tax_text, taxon="GenusA", rank="Genus", action="color_branch", color="#228833"
    )
    print(
        f"  status={styled['status']} action_applied={styled['action_applied']} "
        f"n_rows={styled['n_template_rows']}"
    )
    print(styled["template"])
    out = create_template(
        TemplateSpec(
            template_type="tree_colors",
            label="mono GenusA branches",
            data_rows=[
                {"id": m, "type": "branch", "color": "#228833"}
                for m in styled["group_info"]["member_ids"]
            ],
        ),
        workspace,
        out_path="templates/01_tree_colors_genusA.txt",
        force=True,
    )
    generated.append(Path(out["file"]))

    # 4) 并系类群：默认跳过 / strict 报错 ---------------------------------------
    header("4) 并系类群 GenusD → color_strip（保护性行为）")
    skipped = check_and_style(
        tree_text, tax_text, taxon="GenusD", rank="Genus", action="color_strip", color="#CCBB44"
    )
    print(f"  status={skipped['status']}")
    print(f"  跳过原因：{skipped['skipped_reason']}")
    try:
        check_and_style(
            tree_text, tax_text, taxon="GenusD", rank="Genus", action="color_strip", strict=True
        )
    except TaxonomyError as exc:
        print(f"  strict=True → TaxonomyError：{exc}")

    # 5) 复系类群：同样跳过 -----------------------------------------------------
    header("5) 复系类群 GenusE → highlight（保护性行为）")
    poly_skipped = check_and_style(
        tree_text, tax_text, taxon="GenusE", rank="Genus", action="highlight", color="#EE6677"
    )
    print(f"  status={poly_skipped['status']}")
    print(f"  跳过原因：{poly_skipped['skipped_reason']}")

    # 6) 分类学驱动模板 ---------------------------------------------------------
    header("6) 分类学驱动模板（color_strip by Phylum / binary by Genus）")
    strip = create_template(
        TemplateSpec(
            template_type="color_strip",
            label="Phylum",
            tree=tree_text,
            taxonomy=tax_text,
            column="Phylum",
            palette="tol_vibrant",
            parameters={"STRIP_WIDTH": 30, "LEGEND_POSITION": 4},
        ),
        workspace,
        out_path="templates/02_colorstrip_phylum.txt",
        force=True,
    )
    generated.append(Path(strip["file"]))
    binary = create_template(
        TemplateSpec(
            template_type="binary",
            label="Genus presence",
            tree=tree_text,
            taxonomy=tax_text,
            column="Genus",
            parameters={
                "FIELD_LABELS": [
                    "GenusA",
                    "GenusB",
                    "GenusC",
                    "GenusD",
                    "GenusE",
                    "GenusF",
                    "GenusG",
                ]
            },
        ),
        workspace,
        out_path="templates/03_binary_genus.txt",
        force=True,
    )
    generated.append(Path(binary["file"]))
    for g in (strip, binary):
        _p = Path(g["file"])
        _data_lines = [
            ln
            for ln in _p.read_text(encoding="utf-8").splitlines()
            if ln.strip()
            and not ln.split(None, 1)[0].startswith(
                ("DATASET_", "SEPARATOR", "DATA", "LEGEND", "COLOR", "STRIP", "FIELD")
            )
        ]
        print(f"  已生成：{_p.name}（{len(_data_lines)} 行数据）")
        for w in g["warnings"]:
            print(f"    [警告] {w}")

    # 7) 模板校验 -------------------------------------------------------------
    header("7) 生成模板的 iTOL 规范校验（含 ID 匹配）")
    for path in generated:
        report = validate_template(path.read_text(encoding="utf-8"), tree_text=tree_text)
        flags = [c["level"] for c in report["checks"]]
        verdict = "通过" if report["valid"] else "未通过"
        print(
            f"  {path.name}: {verdict} | header={report['header']} "
            f"| 数据行 {report['n_data_rows']} | ID 匹配 {report['matched_ids']} | {flags}"
        )

    header("完成")
    print(f"  输出目录：{OUT}")
    print("  将 synthetic_32tips.nwk 与其上模板一起上传即可在 iTOL 中渲染（见 iTOL 批量上传器）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
