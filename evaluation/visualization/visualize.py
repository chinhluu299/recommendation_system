"""
visualize.py — Sinh biểu đồ đánh giá cho thesis.

Output:
    hit_rate.png      — Hit@K bar chart  (All / Filter / Intent)
    mrr_ndcg.png      — MRR@K và NDCG@K line chart (All / Filter / Intent)
    model_ranking.png — Task 1: Recall@K, NDCG@K cho 4 mô hình gợi ý

Cách chạy (từ thư mục evaluation/visualization/):
    python visualize.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# 0. Đường dẫn tới dữ liệu
# ─────────────────────────────────────────────────────────────────────────────
HERE         = Path(__file__).parent
BASELINE_V2  = HERE / ".." / "baseline_results_v2.json"
PROPOSED_2   = HERE / ".." / "proposed_results_2.json"
TYPE1_JSON   = HERE / ".." / ".." / "offline" / "baseline" / "results" / "type1_comparison.json"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Load dữ liệu từ JSON
# ─────────────────────────────────────────────────────────────────────────────
baseline  = json.loads(BASELINE_V2.read_text(encoding="utf-8"))
proposed  = json.loads(PROPOSED_2.read_text(encoding="utf-8"))
type1_raw = json.loads(TYPE1_JSON.read_text(encoding="utf-8"))

# Lấy summary theo tập (All / Filter / Intent)
def get_summary(data: list, tag: str) -> dict:
    """Tìm entry summary có tên chứa tag."""
    return next(s for s in data if tag in s["system"])

b_all    = get_summary(baseline["summary"], "(All)")
b_filter = get_summary(baseline["summary"], "(Filter)")
b_intent = get_summary(baseline["summary"], "(Intent)")

p_all    = get_summary(proposed["summary"], "(All)")
p_filter = get_summary(proposed["summary"], "(Filter)")
p_intent = get_summary(proposed["summary"], "(Intent)")

# Giá trị K dùng chung
K_SEARCH  = [10, 20, 50, 100, 200]
K_LABELS  = [f"k={k}" for k in K_SEARCH]

# Hàm trích chỉ số theo K
def vals(entry: dict, metric: str, ks: list) -> list:
    return [entry[f"{metric}@{k}"] for k in ks]

# ─────────────────────────────────────────────────────────────────────────────
# Màu sắc / style nhất quán
# ─────────────────────────────────────────────────────────────────────────────
COLORS = {
    "BM25":     "#8884d8",
    "TF-IDF":   "#82ca9d",
    "Semantic": "#ff8c69",
    "KG+KGAT":  "#ffc658",
}
MARKERS = {"BM25": "o", "TF-IDF": "s", "Semantic": "^", "KG+KGAT": "D"}

SYSTEMS = [
    {"key": "BM25",     "label": "BM25 (Baseline)",     "b": lambda tag: get_summary(baseline["summary"], f"BM25 ({tag})")},
    {"key": "TF-IDF",   "label": "TF-IDF (Baseline)",   "b": lambda tag: get_summary(baseline["summary"], f"TF-IDF ({tag})")},
    {"key": "Semantic", "label": "Semantic (Baseline)",  "b": lambda tag: get_summary(baseline["summary"], f"Semantic ({tag})")},
    {"key": "KG+KGAT",  "label": "KG+KGAT (Proposed)",  "b": lambda tag: get_summary(proposed["summary"], f"KG+KGAT ({tag})")},
]

SUBSETS = [
    {"tag": "All",    "label": "Tập: ALL (Tổng hợp)"},
    {"tag": "Filter", "label": "Tập: FILTER (Lọc thuộc tính)"},
    {"tag": "Intent", "label": "Tập: INTENT (Ngữ nghĩa)"},
]

# ─────────────────────────────────────────────────────────────────────────────
# Figure 1 — Hit@K  (bar chart, giữ nguyên style cũ, load từ JSON)
# ─────────────────────────────────────────────────────────────────────────────
def plot_hit_rate():
    x     = np.arange(len(K_SEARCH))
    width = 0.18
    fig, axes = plt.subplots(1, 3, figsize=(20, 6), sharey=True)
    fig.suptitle(
        "So sánh Hit Rate: BM25 vs TF-IDF vs Semantic (Baseline) vs KG+KGAT (Proposed)",
        fontsize=16, fontweight="bold",
    )

    for i, (ax, sub) in enumerate(zip(axes, SUBSETS)):
        tag = sub["tag"]
        offsets = [-1.5, -0.5, 0.5, 1.5]
        for sys, off in zip(SYSTEMS, offsets):
            entry = sys["b"](tag)
            data  = vals(entry, "hit", K_SEARCH)
            kw = dict(edgecolor="black", linewidth=1.1) if sys["key"] == "KG+KGAT" else {}
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
               ncol=4, fontsize=11, frameon=False)
    plt.tight_layout()
    out = HERE / "hit_rate.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2 — MRR@K và NDCG@K  (line chart, 2 hàng × 3 cột)
# ─────────────────────────────────────────────────────────────────────────────
def plot_mrr_ndcg():
    fig, axes = plt.subplots(2, 3, figsize=(20, 11), sharey="row")
    fig.suptitle(
        "So sánh MRR@K và NDCG@K: Baseline vs KG+KGAT (Proposed)",
        fontsize=16, fontweight="bold",
    )

    x = np.arange(len(K_SEARCH))

    for col, sub in enumerate(SUBSETS):
        tag = sub["tag"]
        for row, metric in enumerate(["mrr", "ndcg"]):
            ax = axes[row][col]

            for sys in SYSTEMS:
                entry = sys["b"](tag)
                data  = vals(entry, metric, K_SEARCH)
                lw = 2.5 if sys["key"] == "KG+KGAT" else 1.8
                ls = "-"  if sys["key"] == "KG+KGAT" else "--"
                ax.plot(x, data,
                        marker=MARKERS[sys["key"]], markersize=7,
                        linewidth=lw, linestyle=ls,
                        color=COLORS[sys["key"]], label=sys["label"])

            # Tiêu đề chỉ ở hàng đầu
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

    # Legend chung
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 1.01),
               ncol=4, fontsize=11, frameon=False)
    plt.tight_layout()
    out = HERE / "mrr_ndcg.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3 — Task 1: Model Ranking  (grouped bar chart)
# ─────────────────────────────────────────────────────────────────────────────
def plot_model_ranking():
    models   = [r["model"].split(" (")[0] for r in type1_raw]   # tên ngắn
    r10  = [r["recall@10"]  for r in type1_raw]
    n10  = [r["ndcg@10"]    for r in type1_raw]
    r20  = [r["recall@20"]  for r in type1_raw]
    n20  = [r["ndcg@20"]    for r in type1_raw]

    # Màu: 3 baseline xám, proposed vàng
    bar_colors = ["#b0b0b0", "#909090", "#707070", "#ffc658"]
    edge_kws   = [dict(edgecolor="none")] * 3 + [dict(edgecolor="black", linewidth=1.3)]

    x     = np.arange(len(models))
    width = 0.2

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        "Task 1 — So sánh mô hình gợi ý cá nhân hoá (Type 1, n=1000 users)",
        fontsize=15, fontweight="bold",
    )

    for ax, (metric_vals, k, ylabel) in zip(
        axes,
        [(r10, 10, "Recall@10"), (n10, 10, "NDCG@10")],
    ):
        bars = ax.bar(x, metric_vals, width * 2,
                      color=bar_colors,
                      **{k2: v2 for d in edge_kws for k2, v2 in d.items()})
        # Riêng proposed phải set riêng
        bars[-1].set_edgecolor("black")
        bars[-1].set_linewidth(1.3)
        for j, (bar, c, ek) in enumerate(zip(bars, bar_colors, edge_kws)):
            bar.set_color(c)
            if j < 3:
                bar.set_edgecolor("none")

        # Gán nhãn giá trị lên đầu cột
        for bar, val in zip(bars, metric_vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.001,
                    f"{val:.4f}", ha="center", va="bottom", fontsize=10)

        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(models, fontsize=11, rotation=10, ha="right")
        ax.yaxis.grid(True, linestyle="--", alpha=0.6)
        ax.set_axisbelow(True)
        ax.set_ylim(0, max(metric_vals) * 1.25)

    # Vẽ lại sạch với bar đơn (fix override issue)
    for ax in axes:
        ax.cla()

    metrics_pairs = [
        (r10, r20, "Recall@K"),
        (n10, n20, "NDCG@K"),
    ]
    k_pairs  = [10, 20]
    x_g      = np.arange(len(models))
    w        = 0.3

    for ax, (vals_k10, vals_k20, ylabel) in zip(axes, metrics_pairs):
        b1 = ax.bar(x_g - w / 2, vals_k10, w, color=bar_colors, label="K=10")
        b2 = ax.bar(x_g + w / 2, vals_k20, w, color=bar_colors, alpha=0.55, label="K=20",
                    hatch="//")

        # Proposed: viền đậm
        b1[-1].set_edgecolor("black"); b1[-1].set_linewidth(1.3)
        b2[-1].set_edgecolor("black"); b2[-1].set_linewidth(1.3)

        # Value labels
        for bar, val in zip(b1, vals_k10):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.0005,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=9)
        for bar, val in zip(b2, vals_k20):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.0005,
                    f"{val:.3f}", ha="center", va="bottom", fontsize=9)

        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_xticks(x_g)
        ax.set_xticklabels(models, fontsize=11, rotation=12, ha="right")
        ax.yaxis.grid(True, linestyle="--", alpha=0.6)
        ax.set_axisbelow(True)
        ax.set_ylim(0, max(max(vals_k10), max(vals_k20)) * 1.3)

    # Custom legend: model màu + K pattern
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    model_labels = ["Random", "Popularity", "MF / SVD", "KGAT (Proposed)"]
    legend_elems = [Patch(facecolor=c, label=m) for c, m in zip(bar_colors, model_labels)]
    legend_elems += [
        Patch(facecolor="white", edgecolor="gray", label="K=10 (solid)"),
        Patch(facecolor="white", edgecolor="gray", hatch="//", label="K=20 (hatch)"),
    ]
    fig.legend(handles=legend_elems, loc="upper center", bbox_to_anchor=(0.5, 1.02),
               ncol=6, fontsize=10, frameon=False)
    plt.tight_layout()
    out = HERE / "model_ranking.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# Figure 4 — Latency comparison  (horizontal bar)
# ─────────────────────────────────────────────────────────────────────────────
def plot_latency():
    systems  = ["TF-IDF", "BM25", "Semantic", "KG+KGAT"]
    latency  = [3.43, 10.25, 17.94, 21937.42]   # ms
    colors   = [COLORS["TF-IDF"], COLORS["BM25"], COLORS["Semantic"], COLORS["KG+KGAT"]]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Latency trung bình mỗi truy vấn (ms)", fontsize=15, fontweight="bold")

    # Left: linear scale (chỉ 3 baseline)
    ax = axes[0]
    ax.barh(systems[:3], latency[:3], color=colors[:3], edgecolor="gray", height=0.5)
    for i, (v, name) in enumerate(zip(latency[:3], systems[:3])):
        ax.text(v + 0.2, i, f"{v:.1f} ms", va="center", fontsize=11)
    ax.set_xlabel("Latency (ms) — Linear", fontsize=12)
    ax.set_title("Baseline (thang tuyến tính)", fontsize=12)
    ax.xaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)

    # Right: log scale (tất cả 4)
    ax = axes[1]
    ax.barh(systems, latency, color=colors, edgecolor="gray", height=0.5)
    for i, (v, name) in enumerate(zip(latency, systems)):
        label = f"{v:,.0f} ms" if v > 1000 else f"{v:.1f} ms"
        ax.text(v * 1.05, i, label, va="center", fontsize=11)
    ax.set_xscale("log")
    ax.set_xlabel("Latency (ms) — Log scale", fontsize=12)
    ax.set_title("Tất cả hệ thống (thang log)", fontsize=12)
    ax.xaxis.grid(True, linestyle="--", alpha=0.6)
    ax.set_axisbelow(True)

    # Annotation
    axes[1].annotate("×2,140 chậm hơn Semantic",
                     xy=(21937, 3), xytext=(500, 2.5),
                     arrowprops=dict(arrowstyle="->", color="red"),
                     fontsize=10, color="red")

    plt.tight_layout()
    out = HERE / "latency.png"
    plt.savefig(out, dpi=300, bbox_inches="tight")
    print(f"Saved: {out}")
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating charts...")
    plot_hit_rate()
    plot_mrr_ndcg()
    plot_model_ranking()
    plot_latency()
    print("Done.")
