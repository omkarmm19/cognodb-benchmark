"""
Report & Visual Charts Generator
----------------------------------
Parses results/raw_metrics.json and generates:
  1. PNG charts in results/charts/
  2. Markdown summary table in results/summary_table.md

Handles:
  - Platforms with status "ok" (real results)
  - Platforms with status "unavailable" (skipped — not shown in charts)
  - The __meta key in the results file
"""

import os
import json
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from tabulate import tabulate

ROOT        = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(ROOT, "results")
CHARTS_DIR  = os.path.join(RESULTS_DIR, "charts")
RAW_PATH    = os.path.join(RESULTS_DIR, "raw_metrics.json")
TABLE_PATH  = os.path.join(RESULTS_DIR, "summary_table.md")

plt.rcParams.update({
    "figure.dpi":         150,
    "font.family":        "sans-serif",
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.grid":          True,
    "grid.alpha":         0.3,
})

PALETTE = ["#4F46E5", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"]


def load_metrics():
    if not os.path.exists(RAW_PATH):
        print(f"[generate_report] {RAW_PATH} not found — run the benchmark first.")
        return None, None
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    meta = raw.pop("__meta", {})
    return raw, meta


def available(data):
    """Return only platforms that were successfully benchmarked."""
    return {k: v for k, v in data.items() if v.get("status") == "ok"}


def generate_charts(data):
    os.makedirs(CHARTS_DIR, exist_ok=True)
    avail = available(data)
    if not avail:
        print("[generate_report] No available platforms — skipping charts.")
        return

    platforms = list(avail.keys())
    colors    = PALETTE[: len(platforms)]

    # ── 1. Ingestion Throughput ────────────────────────────────────────────
    try:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        import numpy as np
        x = np.arange(len(platforms))
        w = 0.35
        nodes_s = [avail[p]["ingest"].get("nodes_per_sec", 0) for p in platforms]
        rels_s  = [avail[p]["ingest"].get("rels_per_sec",  0) for p in platforms]
        ax.bar(x - w/2, nodes_s, w, label="Nodes/sec", color="#6366F1", edgecolor="white", linewidth=0.5)
        ax.bar(x + w/2, rels_s,  w, label="Rels/sec",  color="#10B981", edgecolor="white", linewidth=0.5)
        ax.set_title("Data Ingestion Throughput (Higher is Better)", fontweight="bold")
        ax.set_ylabel("Items per Second")
        ax.set_xticks(x); ax.set_xticklabels(platforms, fontweight="bold")
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "ingest_throughput.png"))
        plt.close()
    except Exception as e:
        print(f"[generate_report] Ingest chart: {e}")

    # ── 2. Traversal Latency p50 / p95 ────────────────────────────────────
    try:
        import numpy as np
        fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
        hops   = ["1_hop", "2_hop", "3_hop"]
        labels = ["1-Hop (ms)", "2-Hop (ms)", "3-Hop (ms)"]
        for i, (hop, title) in enumerate(zip(hops, labels)):
            p50 = [avail[p]["traversals"].get(hop, {}).get("p50_ms") or 0 for p in platforms]
            p95 = [avail[p]["traversals"].get(hop, {}).get("p95_ms") or 0 for p in platforms]
            x = np.arange(len(platforms)); w = 0.35
            axes[i].bar(x - w/2, p50, w, label="p50", color="#3B82F6", edgecolor="white")
            axes[i].bar(x + w/2, p95, w, label="p95", color="#F97316", edgecolor="white")
            axes[i].set_title(title, fontweight="bold")
            axes[i].set_xticks(x)
            axes[i].set_xticklabels(platforms, rotation=15, ha="right", fontsize=9)
            axes[i].set_ylabel("Latency ms (lower = better)")
            axes[i].legend(fontsize=8)
        fig.suptitle("Graph Traversal Latency (p50 vs p95)", fontweight="bold", y=1.02)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "traversal_latencies.png"), bbox_inches="tight")
        plt.close()
    except Exception as e:
        print(f"[generate_report] Traversal chart: {e}")

    # ── 3. Concurrency Scaling ─────────────────────────────────────────────
    try:
        fig, ax = plt.subplots(figsize=(8, 5))
        for idx, p in enumerate(platforms):
            conc = avail[p].get("concurrency", {})
            pts  = sorted([(v["clients"], v["throughput_qps"])
                           for v in conc.values() if "clients" in v and "throughput_qps" in v])
            if pts:
                xs, ys = zip(*pts)
                ax.plot(xs, ys, marker="o", linewidth=2.5, label=p, color=colors[idx])
        ax.set_title("Mixed Workload Concurrency Scaling (80% Read / 20% Write)", fontweight="bold")
        ax.set_xlabel("Concurrent Clients"); ax.set_ylabel("Throughput QPS (higher = better)")
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "concurrency_scaling.png"))
        plt.close()
    except Exception as e:
        print(f"[generate_report] Concurrency chart: {e}")

    print(f"[generate_report] Charts saved → {CHARTS_DIR}")


def generate_markdown_tables(data, meta=None):
    avail   = available(data)
    unavail = {k: v for k, v in data.items() if v.get("status") != "ok"}
    platforms = list(avail.keys())

    md = "## 📊 Benchmark Results\n\n"
    if meta:
        md += (
            f"> **Run config:** {meta.get('measured_iters', '?')} measured iterations, "
            f"{meta.get('warmup_iters', '?')} warmup | "
            f"Dataset: {meta.get('dataset_nodes', 37700):,} nodes, "
            f"{meta.get('dataset_edges', 394213):,} edges | "
            f"Seed: {meta.get('random_seed', 42)} | "
            f"Generated: {meta.get('generated_at', 'N/A')}\n\n"
        )

    if unavail:
        md += "### ⚠️ Platforms Not Benchmarked\n\n"
        rows = [[k, v.get("reason", "Connection failed or not configured")]
                for k, v in unavail.items()]
        md += tabulate(rows, headers=["Platform", "Reason"], tablefmt="github")
        md += "\n\n"

    if not platforms:
        md += "_No platforms produced results._\n"
        with open(TABLE_PATH, "w") as f: f.write(md)
        return md

    # 1. Ingestion
    ingest_rows = []
    for p in platforms:
        ing = avail[p].get("ingest", {})
        ingest_rows.append([
            p,
            f"{ing.get('total_nodes', 0):,}",
            f"{ing.get('total_edges', 0):,}",
            f"{ing.get('wall_clock_time_s', 0):.1f}s",
            f"{ing.get('nodes_per_sec', 0):,.0f}",
            f"{ing.get('rels_per_sec',  0):,.0f}",
        ])
    md += "### 1. Data Ingestion Performance\n\n"
    md += tabulate(ingest_rows,
                   headers=["Platform","Nodes Loaded","Edges Loaded","Wall-Clock Time","Nodes/sec","Rels/sec"],
                   tablefmt="github")
    md += "\n\n"

    # 2. Traversals
    trav_rows = []
    for p in platforms:
        tr = avail[p].get("traversals", {})
        def _fmt(hop):
            d = tr.get(hop, {})
            p50 = d.get("p50_ms"); p95 = d.get("p95_ms")
            if p50 is None: return "N/A"
            return f"{p50:.1f} / {p95:.1f}"
        trav_rows.append([p, _fmt("1_hop"), _fmt("2_hop"), _fmt("3_hop")])
    md += "### 2. Traversal Latency (p50 / p95 ms — lower is better)\n\n"
    md += tabulate(trav_rows,
                   headers=["Platform","1-Hop p50/p95","2-Hop p50/p95","3-Hop p50/p95"],
                   tablefmt="github")
    md += "\n\n"

    # 3. Lookups & Aggregation
    look_rows = []
    for p in platforms:
        lk  = avail[p].get("lookups", {})
        agg = avail[p].get("aggregations", {}).get("aggregation_group_by", {})
        def _f(d):
            p50 = d.get("p50_ms"); p95 = d.get("p95_ms")
            if p50 is None: return "N/A"
            return f"{p50:.1f} / {p95:.1f}"
        look_rows.append([p, _f(lk.get("point_lookup",{})), _f(lk.get("indexed_lookup",{})), _f(agg)])
    md += "### 3. Lookups & Aggregations (p50 / p95 ms — lower is better)\n\n"
    md += tabulate(look_rows,
                   headers=["Platform","Point Lookup","Indexed Filter","Group-by Aggregation"],
                   tablefmt="github")
    md += "\n\n"

    # 4. Concurrency
    conc_rows = []
    for p in platforms:
        c = avail[p].get("concurrency", {})
        def _c(key):
            d = c.get(key, {})
            qps = d.get("throughput_qps"); p95 = d.get("p95_ms")
            if qps is None: return "N/A"
            return f"{qps:,.0f} QPS  p95={p95:.0f}ms"
        conc_rows.append([p, _c("concurrency_1"), _c("concurrency_10"), _c("concurrency_40")])
    md += "### 4. Mixed Concurrency Throughput (80% Read / 20% Write)\n\n"
    md += tabulate(conc_rows,
                   headers=["Platform","1 Client","10 Clients","40 Clients"],
                   tablefmt="github")
    md += "\n\n"

    # 5. Footprint
    fp_rows = []
    for p in platforms:
        fp = avail[p].get("footprint", {})
        fp_rows.append([
            p,
            fp.get("deployment", fp.get("vCPU", "—")),
            str(fp.get("RAM_allocated_MB", fp.get("RAM_allocated", "—"))),
            fp.get("memory_usage", "—"),
        ])
    md += "### 5. Resource Footprint\n\n"
    md += tabulate(fp_rows,
                   headers=["Platform","Deployment","RAM (MB)","Memory Usage"],
                   tablefmt="github")
    md += "\n\n"

    with open(TABLE_PATH, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[generate_report] Summary table → {TABLE_PATH}")
    return md


def generate_all():
    data, meta = load_metrics()
    if data is not None:
        generate_charts(data)
        return generate_markdown_tables(data, meta)
    return ""


if __name__ == "__main__":
    generate_all()
