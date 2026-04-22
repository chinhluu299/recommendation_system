"""Sinh biểu đồ Hit@K, MRR@K, NDCG@K cho báo cáo."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np


HERE        = Path(__file__).parent
BASELINE_F  = HERE / ".." / "baseline_results_v2.json"
PROPOSED_F  = HERE / ".." / "proposed_results_2.json"

baseline = json.loads(BASELINE_F.read_text(encoding="utf-8"))
proposed = json.loads(PROPOSED_F.read_text(encoding="utf-8"))


def get_summary(data: list, tag: str) -> dict:
    return next(s for s in data if tag in s["system"])


K_SEARCH = [10, 20, 50, 100, 200]
K_LABELS = [f"k={k}" for k in K_SEARCH]


def vals(entry: dict, metric: str, ks: list) -> list:
    return [entry[f"{metric}@{k}"] for k in ks]


COLORS = {
    "BM25":           "#8884d8",
    "Semantic":       "#82ca9d",
    "LLM+Cypher":     "#ff8c69",
    "LLM+Cypher+KGAT":"#ffc658",
}
MARKERS = {
    "BM25":           "o",
    "Semantic":       "s",
    "LLM+Cypher":     "^",
    "LLM+Cypher+KGAT":"D",
}

SYSTEMS = [
    {
        "key":   "BM25",
        "label": "BM25 (Baseline)",
        "b":     lambda tag: get_summary(baseline["summary"], f"BM25 ({tag})"),
    },
    {
        "key":   "Semantic",
        "label": "Semantic Search (Baseline)",
        "b":     lambda tag: get_summary(baseline["summary"], f"Semantic ({tag})"),
    },
    {
        "key":   "LLM+Cypher",
        "label": "LLM+Cypher (Proposed)",
        "b":     lambda tag: get_summary(proposed["summary"], f"Proposed ({tag})"),
    },
    {
        "key":   "LLM+Cypher+KGAT",
        "label": "LLM+Cypher+KGAT (Proposed)",
        "b":     lambda tag: get_summary(proposed["summary"], f"Proposed+KGAT ({tag})"),
    },
]

SUBSETS = [
    {"tag": "All",    "label": "Tập: ALL (Tổng hợp)"},
    {"tag": "Filter", "label": "Tập: FILTER (Lọc thuộc tính)"},
    {"tag": "Intent", "label": "Tập: INTENT (Ngữ nghĩa)"},
]


def plot_hit_rate():
    x     = np.arange(len(K_SEARCH))
    width = 0.18
    fig, axes = plt.subplots(1, 3, figsize=(20, 6), sharey=True)
    fig.suptitle(
        "Hit Rate",
        fontsize=12, fontweight="bold",
    )

    for i, (ax, sub) in enumerate(zip(axes, SUBSETS)):
        tag = sub["tag"]
        offsets = [-1.5, -0.5, 0.5, 1.5]
        for sys, off in zip(SYSTEMS, offsets):
            entry = sys["b"](tag)
            data  = vals(entry, "hit", K_SEARCH)
            is_proposed = "Proposed" in sys["label"]
            kw = dict(edgecolor="black", linewidth=1.1) if is_proposed else {}
            ax.bar(x + off * width, data, width,
                   label=sys["label"], color=COLORS[sys["key"]], **kw)

        ax.set_title(sub["label"], fontsize=13, fontweight="bold", pad=12)
        ax.set_xlabel("Giá trị K (Top-K)", fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(K_LABELS, fontsize=11)
        if i == 0:
            ax.set_ylabel("Hit Rate", fontsize=12)
        ax.yaxis.grid(True, linestyle="--", alpha=0.6)
        ax.set_axisbelow(True)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.01),
               ncol=4, fontsize=10, frameon=False)
    plt.tight_layout()
    out = HERE / "hit_rate.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


def plot_mrr_ndcg():
    fig, axes = plt.subplots(2, 3, figsize=(20, 11), sharey="row")
    fig.suptitle(
        "So sánh MRR@K và NDCG@K: BM25 vs Semantic (Baseline) vs LLM+Cypher vs LLM+Cypher+KGAT (Proposed)",
        fontsize=14, fontweight="bold",
    )

    x = np.arange(len(K_SEARCH))

    for col, sub in enumerate(SUBSETS):
        tag = sub["tag"]
        for row, metric in enumerate(["mrr", "ndcg"]):
            ax = axes[row][col]

            for sys in SYSTEMS:
                entry = sys["b"](tag)
                data  = vals(entry, metric, K_SEARCH)
                is_proposed = "Proposed" in sys["label"]
                lw = 2.5 if is_proposed else 1.8
                ls = "-"  if is_proposed else "--"
                ax.plot(x, data,
                        marker=MARKERS[sys["key"]], markersize=7,
                        linewidth=lw, linestyle=ls,
                        color=COLORS[sys["key"]], label=sys["label"])

            if row == 0:
                ax.set_title(sub["label"], fontsize=13, fontweight="bold", pad=10)


            ax.set_xticks(x)
            ax.set_xticklabels(K_LABELS, fontsize=10)
            ax.set_xlabel("Giá trị K (Top-K)", fontsize=11)

            metric_name = "MRR" if metric == "mrr" else "NDCG"
            if col == 0:
                ax.set_ylabel(f"{metric_name}@K", fontsize=12)

            ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
            ax.yaxis.grid(True, linestyle="--", alpha=0.6)
            ax.set_axisbelow(True)

    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.01),
               ncol=4, fontsize=10, frameon=False)
    plt.tight_layout()
    out = HERE / "mrr_ndcg.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


if __name__ == "__main__":
    print("Generating charts...")
    plot_hit_rate()
    plot_mrr_ndcg()
    print("Done.")
