#!/usr/bin/env python
"""端到端示例 02：出版级出图 —— 130 末端高信息密度注释模板组合。

完全离线运行（不调用 iTOL 网络 API），使用 ``examples/data/synthetic_130tips.*``：

1. 解析 130 末端树并输出统计信息；
2. 多列热图（HEATMAP）：5 个数值性状一图呈现（FIELD_LABELS / 渐变配色）；
3. 简单柱状图（SIMPLEBAR）：基因组大小 genome_size_Mb；
4. 渐变条（GRADIENT）：丰度 abundance_log10（归一化到 0–1）；
5. 分类学驱动色带（COLORSTRIP）：按 Phylum 着色（tol_vibrant 调色板）；
6. 按门分支着色（TREE_COLORS，type=branch）；
7. 特殊宏类群 LBCA（细菌最近共同祖先）分支着色；
8. 全部模板 iTOL 规范校验（含 ID 匹配）。

运行（在项目根目录）：
    python examples/02_publication_style.py
输出目录：
    examples/output/02_publication_style/
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from itol_mcp.services.taxonomy_service import check_and_style, check_monophyly
from itol_mcp.services.template_service import (
    TemplateSpec,
    create_template,
    validate_template,
)
from itol_mcp.services.tree_service import summarize
from itol_mcp.services.workspace_service import Workspace
from itol_mcp.utils.color_tools import assign_colors

# 项目根目录定位（兼容从任意工作目录启动）
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "examples" / "data"
OUT = ROOT / "examples" / "output" / "02_publication_style"

TREE_FILE = DATA / "synthetic_130tips.nwk"
TAXONOMY_FILE = DATA / "synthetic_130tips_taxonomy.csv"
TRAITS_FILE = DATA / "synthetic_130tips_traits.csv"

TRAIT_COLUMNS = ["GC_percent", "genome_size_Mb", "optimal_temp", "growth_rate", "abundance_log10"]
TRAIT_LABELS = ["GC%", "Genome (Mb)", "Optimal T (°C)", "Growth rate", "Log10 abundance"]


def header(title: str) -> None:
    print("\n" + "=" * 64)
    print(" " + title)
    print("=" * 64)


def main() -> None:
    tree_text = TREE_FILE.read_text(encoding="utf-8")
    tax_text = TAXONOMY_FILE.read_text(encoding="utf-8")
    traits = pd.read_csv(TRAITS_FILE)
    workspace = Workspace(OUT)
    generated: list[Path] = []

    # 1) 树统计 ------------------------------------------------------------
    header("1) 树统计信息（synthetic_130tips.nwk）")
    info = summarize(tree_text)
    print(f"  格式：{info.format}；末端 {info.n_tips}；内部节点 {info.n_internal}")
    print(f"  最大深度 {info.max_depth}；总分支长 {info.total_branch_length}")
    for w in info.warnings:
        print(f"  [警告] {w}")

    # 2) 多列热图 ----------------------------------------------------------
    header("2) 多列热图（DATASET_HEATMAP，5 个数值性状）")
    heat_rows: list[dict] = []
    for _, row in traits.iterrows():
        heat_rows.append({"id": row["id"], **{c: float(row[c]) for c in TRAIT_COLUMNS}})
    heat = create_template(
        TemplateSpec(
            template_type="heatmap",
            label="Genomic traits",
            data_rows=heat_rows,
            parameters={
                "FIELD_LABELS": TRAIT_LABELS,
                "WIDTH": 400,
                "STRIP_WIDTH": 20,
                "COLOR_MIN": "#2166AC",
                "COLOR_MID": "#F7F7F7",
                "COLOR_MAX": "#B2182B",
                "USE_MID_COLOR": 1,
                "LEGEND_POSITION": 4,
            },
        ),
        workspace,
        out_path="templates/01_heatmap_traits.txt",
        force=True,
    )
    generated.append(Path(heat["file"]))
    print(f"  已生成：{Path(heat['file']).name}（{heat['n_rows']} 行 × 6 列）")

    # 3) 柱状图 ------------------------------------------------------------
    header("3) 柱状图（DATASET_SIMPLEBAR，genome_size_Mb）")
    bar_rows = [
        {"id": row["id"], "bar_height": float(row["genome_size_Mb"])}
        for _, row in traits.iterrows()
    ]
    bar = create_template(
        TemplateSpec(
            template_type="simple_bar",
            label="Genome size",
            data_rows=bar_rows,
            parameters={"BAR_WIDTH": 10, "LEGEND_TITLE": "genome_size_Mb", "LEGEND_POSITION": 4},
        ),
        workspace,
        out_path="templates/02_simplebar_genome.txt",
        force=True,
    )
    generated.append(Path(bar["file"]))
    print(f"  已生成：{Path(bar['file']).name}（{bar['n_rows']} 行）")

    # 4) 渐变条 ------------------------------------------------------------
    header("4) 渐变条（DATASET_GRADIENT，abundance_log10 归一化）")
    values = traits["abundance_log10"].astype(float)
    vmin, vmax = float(values.min()), float(values.max())
    grad_rows = [
        {"id": row["id"], "value": round((float(row["abundance_log10"]) - vmin) / (vmax - vmin), 6)}
        for _, row in traits.iterrows()
    ]
    grad = create_template(
        TemplateSpec(
            template_type="gradient",
            label="Abundance",
            data_rows=grad_rows,
            parameters={"STRIP_WIDTH": 15, "LEGEND_TITLE": "abundance_log10", "LEGEND_POSITION": 4},
        ),
        workspace,
        out_path="templates/03_gradient_abundance.txt",
        force=True,
    )
    generated.append(Path(grad["file"]))
    print(f"  已生成：{Path(grad['file']).name}（{grad['n_rows']} 行，范围 {vmin:.2f}–{vmax:.2f}）")

    # 5) 分类学驱动色带 -----------------------------------------------------
    header("5) 分类学驱动色带（DATASET_COLORSTRIP，按 Phylum，tol_vibrant）")
    strip = create_template(
        TemplateSpec(
            template_type="color_strip",
            label="Phylum",
            tree=tree_text,
            taxonomy=tax_text,
            column="p",
            palette="tol_vibrant",
            parameters={"STRIP_WIDTH": 40, "LEGEND_POSITION": 4},
        ),
        workspace,
        out_path="templates/04_colorstrip_phylum.txt",
        force=True,
    )
    generated.append(Path(strip["file"]))
    print(f"  已生成：{Path(strip['file']).name}（{strip['n_rows']} 行）")

    # 6) 按门分支着色 --------------------------------------------------------
    header("6) 分支着色（TREE_COLORS，type=branch，按 Phylum）")
    tax_df = pd.read_csv(TAXONOMY_FILE)
    phyla = sorted(tax_df["p"].dropna().unique())
    phylum_color, _ = assign_colors(phyla, palette="tol_vibrant")
    color_map = dict(zip(phyla, phylum_color, strict=True))
    tc_rows = [
        {"id": row["id"], "type": "branch", "color": color_map[row["p"]]}
        for _, row in tax_df.iterrows()
    ]
    tcolors = create_template(
        TemplateSpec(
            template_type="tree_colors",
            label="phylum branches",
            data_rows=tc_rows,
            parameters={"STRIP_WIDTH": 10},
        ),
        workspace,
        out_path="templates/05_tree_colors_phylum.txt",
        force=True,
    )
    generated.append(Path(tcolors["file"]))
    print(
        f"  已生成：{Path(tcolors['file']).name}（{tcolors['n_rows']} 行，"
        f"{len(phyla)} 个门：{', '.join(phyla)}）"
    )

    # 7) 特殊宏类群 LBCA ------------------------------------------------------
    header("7) 宏类群 LBCA（细菌最近共同祖先）单系性 + 分支着色")
    lbca = check_monophyly(tree_text, tax_text, rank="Domain", taxa=["LBCA"])[0]
    print(f"  LBCA status={lbca['status']} member_count={lbca['member_count']}")
    styled = check_and_style(
        tree_text, tax_text, taxon="LBCA", rank="Domain", action="color_branch", color="#0077BB"
    )
    out = create_template(
        TemplateSpec(
            template_type="tree_colors",
            label="LBCA branches",
            data_rows=[
                {"id": m, "type": "branch", "color": "#0077BB"}
                for m in styled["group_info"]["member_ids"]
            ],
        ),
        workspace,
        out_path="templates/06_tree_colors_lbca.txt",
        force=True,
    )
    generated.append(Path(out["file"]))
    print(f"  已生成：{Path(out['file']).name}（{styled['n_template_rows']} 行）")

    # 8) 模板校验 -------------------------------------------------------------
    header("8) 全部模板 iTOL 规范校验（含 ID 与树匹配）")
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
    print("  iTOL 中上传 synthetic_130tips.nwk 并附加上述 6 个模板即可复现出版级图。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
