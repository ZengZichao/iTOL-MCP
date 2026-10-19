#!/usr/bin/env python
"""生成示例合成数据（examples/data/，与 PyiTOL 参考数据同构）。

产出：
- ``synthetic_130tips.nwk``：130 末端随机合并树（嵌入式 GTDB 风格名称，8 个门）
- ``synthetic_130tips_taxonomy.csv``：id,d,p,c,o,f,g,s 分类表
- ``synthetic_130tips_traits.csv``：id + 5 个数值性状（热图/柱状/渐变用）
- ``synthetic_32tips.nwk``：32 末端固定拓扑树（含 mono/para/poly 三分类演示类群）
- ``synthetic_32tips_taxonomy.csv``：32 行分类表（id, Domain, Phylum, Class, Order, Family, Genus）

用法：
    python examples/scripts/generate_synthetic_data.py [输出目录，默认 examples/data]
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pandas as pd

# 130 tips 的 8 个门（名称取自常见细菌分类学命名风格，仅作示例）
PHYLA = [
    (
        "Proteobacteria",
        "Gammaproteobacteria",
        "Enterobacterales",
        "Enterobacteriaceae",
        "Escherichia",
    ),
    ("Proteobacteria", "Alphaproteobacteria", "Rhizobiales", "Rhizobiaceae", "Rhizobium"),
    ("Firmicutes", "Bacilli", "Bacillales", "Bacillaceae", "Bacillus"),
    ("Firmicutes", "Clostridia", "Clostridiales", "Clostridiaceae", "Clostridium"),
    ("Actinobacteria", "Actinomycetia", "Streptomycetales", "Streptomycetaceae", "Streptomyces"),
    ("Bacteroidota", "Bacteroidia", "Bacteroidales", "Bacteroidaceae", "Bacteroides"),
    ("Pseudomonadota", "Gammaproteobacteria", "Pseudomonadales", "Pseudomonadaceae", "Pseudomonas"),
    ("Cyanobacteria", "Cyanophyceae", "Synechococcales", "Synechococcaceae", "Synechococcus"),
]

GENI_SPP = {
    "Escherichia": "coli",
    "Rhizobium": "leguminosarum",
    "Bacillus": "subtilis",
    "Clostridium": "perfringens",
    "Streptomyces": "coelicolor",
    "Bacteroides": "fragilis",
    "Pseudomonas": "aeruginosa",
    "Synechococcus": "elongatus",
}


def q(label: str) -> str:
    """Newick 单引号标签：保留下划线（未引用的标签在 Newick 规范中下划线按空格解释）。"""
    return f"'{label}'"


def coalescent_tree_text(names: list[str], rng: random.Random, seed: int) -> str:
    """随机合并生成有根二叉树（ultrametric-ish 分支长度），返回 Newick 文本。"""
    rng = random.Random(seed)
    nodes: list[tuple[str, float]] = [(q(n), 0.0) for n in names]
    index = len(names)
    while len(nodes) > 1:
        i, j = rng.sample(range(len(nodes)), 2)
        a, da = nodes[i]
        b, db = nodes[j]
        branch = rng.uniform(0.05, 0.5)
        parent: tuple[str, float] = (
            f"({a}:{branch:.4f},{b}:{branch:.4f})",
            max(da, db) + branch,
        )
        nodes.pop(max(i, j))
        nodes.pop(min(i, j))
        nodes.append(parent)
        index += 1
    ((root, _),) = nodes
    return root + ";\n"


def embedded_130_name(seq: int, phylum: tuple[str, str, str, str, str]) -> str:
    """嵌入式 GTDB 风格名称：GCA_<n>.1_d_Bacteria_p_..._g_..._s_..."""
    p, c, o, f, g = phylum
    return f"GCA_{seq:08d}.1_d_Bacteria_p_{p}_c_{c}_o_{o}_f_{f}_g_{g}_s_{g}_{GENI_SPP[g]}"


def build_130() -> None:
    rng = random.Random(42)
    names: list[str] = []
    rows: list[dict[str, str]] = []
    seq = 1
    # 8 个门各配约 16 个末端（最后一个门补足 130）
    per_phylum = [16] * 7 + [18]
    for phylum, count in zip(PHYLA, per_phylum, strict=True):
        p, c, o, f, g = phylum
        for _ in range(count):
            name = embedded_130_name(seq, phylum)
            names.append(name)
            rows.append(
                {
                    "id": name,
                    "d": "Bacteria",
                    "p": p,
                    "c": c,
                    "o": o,
                    "f": f,
                    "g": g,
                    "s": f"{g}_{GENI_SPP[g]}",
                }
            )
            seq += 1
    assert len(names) == 130, len(names)

    tree_text = coalescent_tree_text(names, rng, 42)
    (DATA_DIR / "synthetic_130tips.nwk").write_text(tree_text, encoding="utf-8")
    pd.DataFrame(rows).to_csv(DATA_DIR / "synthetic_130tips_taxonomy.csv", index=False)

    # 数值性状
    rng2 = random.Random(7)
    trait_rows: list[dict[str, object]] = []
    for row in rows:
        trait_rows.append(
            {
                "id": row["id"],
                "GC_percent": round(rng2.uniform(30, 70), 2),
                "genome_size_Mb": round(rng2.uniform(1.5, 8.0), 2),
                "optimal_temp": round(rng2.uniform(20, 45), 1),
                "growth_rate": round(rng2.uniform(0.1, 2.0), 3),
                "abundance_log10": round(rng2.uniform(-3, 4), 2),
            }
        )
    pd.DataFrame(trait_rows).to_csv(DATA_DIR / "synthetic_130tips_traits.csv", index=False)
    print(f"[130] {len(names)} tips + taxonomy + traits 已写入 {DATA_DIR}")


def build_32() -> None:
    """固定拓扑（32 末端）：A/B/C/F/G 单系、D 并系（clade 内多出外群 E1）、E 复系（E1/E2/E3 分散）。

    拓扑：(((A-clade,B-clade),(C-clade,D-clade)),((F-clade,G-clade),(E2,E3)))
    规模：A6 + B6 + C6 + (D3+E1) + F5 + G3 + E2 + E3 = 32 tips。
    """

    def clade(prefix: str, count: int, extra: tuple[str, ...] = ()) -> str:
        tips = [f"{prefix}{i}" for i in range(1, count + 1)] + list(extra)
        return "(" + ",".join(f"{q(t)}:0.1" for t in tips) + "):0.05"

    def tip(name: str) -> str:
        return f"{q(name)}:0.1"

    a = clade("A", 6)  # GenusA 单系
    b = clade("B", 6)  # GenusB 单系
    c = clade("C", 6)  # GenusC 单系
    d = clade("D", 3, extra=("E1",))  # GenusD 并系（clade 内多出外群 E1）
    f = clade("F", 5)  # GenusF 单系
    g = clade("G", 3)  # GenusG 单系（G1–G3 同一 clade）
    e2, e3 = tip("E2"), tip("E3")  # GenusE 复系（E1/E2/E3 分散于不同谱系）
    tree = f"((({a},{b}),({c},{d})),(({f},{g}),({e2},{e3})));"
    (DATA_DIR / "synthetic_32tips.nwk").write_text(tree + "\n", encoding="utf-8")

    def rows_of(prefix: str, n: int) -> list[dict[str, str]]:
        return [
            {
                "id": f"{prefix}{i}",
                "Domain": "Bacteria",
                "Phylum": "Pseudomonadota",
                "Class": "Gammaproteobacteria",
                "Order": "Enterobacterales",
                "Family": "Enterobacteriaceae",
                "Genus": f"Genus{prefix}",
            }
            for i in range(1, n + 1)
        ]

    e_row = {
        "Domain": "Bacteria",
        "Phylum": "Pseudomonadota",
        "Class": "Gammaproteobacteria",
        "Order": "Enterobacterales",
        "Family": "Enterobacteriaceae",
    }
    rows = rows_of("A", 6) + rows_of("B", 6) + rows_of("C", 6)
    rows += rows_of("D", 3) + rows_of("F", 5) + rows_of("G", 3)
    rows += [
        {"id": "E1", **e_row, "Genus": "GenusE"},
        {"id": "E2", **e_row, "Genus": "GenusE"},
        {"id": "E3", **e_row, "Genus": "GenusE"},
    ]
    assert len(rows) == 32, len(rows)
    pd.DataFrame(rows).to_csv(DATA_DIR / "synthetic_32tips_taxonomy.csv", index=False)

    # 校验：GenusD 应为 para（clade d 含外群 E1），GenusE 应为 poly（E1/E2/E3 分散）
    counts = {"A": 6, "B": 6, "C": 6, "D": 3, "E": 3, "F": 5, "G": 3}
    print(f"[32] 32 tips 已写入 {DATA_DIR}；类群规模：{counts}")
    print("    预期 check_monophyly：GenusA/B/C/F/G = mono，GenusD = para，GenusE = poly")


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        DATA_DIR = Path(sys.argv[1])
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    build_130()
    build_32()
    print("完成。目录：", DATA_DIR)
