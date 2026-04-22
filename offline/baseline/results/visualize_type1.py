"""
visualize_type1.py — Vẽ biểu đồ so sánh kết quả đánh giá offline (Loại 1).

Cách chạy (từ thư mục results/):
    python visualize_type1.py

Hoặc từ thư mục gốc dự án:
    python offline/baseline/results/visualize_type1.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# 1. Đọc dữ liệu
# ─────────────────────────────────────────────────────────────────────────────

DATA_FILE = Path(__file__).parent / "type1_comparison.json"
data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

# Rút gọn tên mô hình (bỏ phần epoch/recall trong ngoặc)
def shorten_name(name: str) -> str:
    return name.split(" (")[0]

model_names  = [shorten_name(d["model"]) for d in data]
recall_at_10 = [d["recall@10"] for d in data]
recall_at_20 = [d["recall@20"] for d in data]
ndcg_at_10   = [d["ndcg@10"]   for d in data]
ndcg_at_20   = [d["ndcg@20"]   for d in data]

n_models = len(model_names)

# ─────────────────────────────────────────────────────────────────────────────
# 2. Cài đặt màu sắc và style
# ─────────────────────────────────────────────────────────────────────────────

COLORS = ["#B0BEC5", "#90CAF9", "#66BB6A", "#EF5350"]  # xám, xanh nhạt, xanh lá, đỏ
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# ─────────────────────────────────────────────────────────────────────────────
# 3. Vẽ biểu đồ
# ─────────────────────────────────────────────────────────────────────────────

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Loại 1 — So sánh Offline Recall & NDCG", fontsize=14, fontweight="bold", y=1.01)

x = np.arange(n_models)
bar_width = 0.35

for ax, (vals_k10, vals_k20, metric_label) in zip(axes, [
    (recall_at_10, recall_at_20, "Recall"),
    (ndcg_at_10,   ndcg_at_20,   "NDCG"),
]):
    bars10 = ax.bar(x - bar_width / 2, vals_k10, width=bar_width,
                    color=COLORS, label=f"{metric_label}@10", alpha=0.85)
    bars20 = ax.bar(x + bar_width / 2, vals_k20, width=bar_width,
                    color=COLORS, label=f"{metric_label}@20", alpha=0.45, hatch="//")

    # Ghi giá trị lên đầu mỗi cột
    for bar in list(bars10) + list(bars20):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + 0.001,
            f"{height:.3f}",
            ha="center", va="bottom", fontsize=8.5,
        )

    ax.set_title(f"{metric_label}@K", fontsize=12)
    ax.set_ylabel("Giá trị", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(model_names, fontsize=10)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.3f"))
    ax.set_ylim(0, max(vals_k20) * 1.25)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # Legend phân biệt @10 và @20
    from matplotlib.patches import Patch
    legend_handles = [
        Patch(facecolor="gray", alpha=0.85, label=f"{metric_label}@10"),
        Patch(facecolor="gray", alpha=0.45, hatch="//", label=f"{metric_label}@20"),
    ]
    ax.legend(handles=legend_handles, fontsize=9)

plt.tight_layout()

# ─────────────────────────────────────────────────────────────────────────────
# 4. Lưu file
# ─────────────────────────────────────────────────────────────────────────────

out_path = Path(__file__).parent / "type1_comparison.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight")
print(f"Đã lưu biểu đồ: {out_path}")
plt.show()
