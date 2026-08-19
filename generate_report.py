"""
Report & Visual Charts Generator
--------------------------------
Parses results/raw_metrics.json and generates:
1. Formatted Markdown tables for README (Section 5.2 metrics)
2. High-resolution matplotlib/seaborn charts saved in results/charts/
"""

import os
import json
import matplotlib.pyplot as plt
import numpy as np
from tabulate import tabulate

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
CHARTS_DIR = os.path.join(RESULTS_DIR, "charts")
RAW_METRICS_PATH = os.path.join(RESULTS_DIR, "raw_metrics.json")
SUMMARY_TABLE_PATH = os.path.join(RESULTS_DIR, "summary_table.md")

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'Helvetica, Arial, DejaVu Sans'
plt.rcParams['axes.edgecolor'] = '#CCCCCC'
plt.rcParams['axes.linewidth'] = 0.8

def load_metrics():
    if not os.path.exists(RAW_METRICS_PATH):
        print(f"Metrics file {RAW_METRICS_PATH} not found.")
        return None
    with open(RAW_METRICS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_charts(data):
    os.makedirs(CHARTS_DIR, exist_ok=True)
    platforms = list(data.keys())
    if not platforms:
        return

    # Palette
    colors = ['#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']

    # 1. Ingest Throughput Chart
    try:
        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=300)
        x = np.arange(len(platforms))
        width = 0.35
        nodes_sec = [data[p].get("ingest", {}).get("nodes_per_sec", 0) for p in platforms]
        rels_sec = [data[p].get("ingest", {}).get("rels_per_sec", 0) for p in platforms]

        ax.bar(x - width/2, nodes_sec, width, label='Nodes/sec', color='#6366F1', edgecolor='black', linewidth=0.5)
        ax.bar(x + width/2, rels_sec, width, label='Rels/sec', color='#10B981', edgecolor='black', linewidth=0.5)

        ax.set_title('Data Ingestion Throughput (Higher is Better)', fontsize=13, fontweight='bold', pad=15)
        ax.set_ylabel('Items per Second')
        ax.set_xticks(x)
        ax.set_xticklabels(platforms, fontweight='semibold')
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "ingest_throughput.png"))
        plt.close()
    except Exception as e:
        print(f"Ingest chart note: {e}")

    # 2. Traversal Latency Chart (p50 & p95)
    try:
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), dpi=300)
        hops = ["1_hop", "2_hop", "3_hop"]
        hop_titles = ["1-Hop Traversal (ms)", "2-Hop Traversal (ms)", "3-Hop Traversal (ms)"]

        for idx, hop in enumerate(hops):
            p50 = [data[p].get("traversals", {}).get(hop, {}).get("p50_ms", 0) for p in platforms]
            p95 = [data[p].get("traversals", {}).get(hop, {}).get("p95_ms", 0) for p in platforms]
            
            x = np.arange(len(platforms))
            w = 0.35
            axes[idx].bar(x - w/2, p50, w, label='p50', color='#3B82F6', edgecolor='black', linewidth=0.5)
            axes[idx].bar(x + w/2, p95, w, label='p95', color='#F97316', edgecolor='black', linewidth=0.5)
            axes[idx].set_title(hop_titles[idx], fontsize=11, fontweight='bold')
            axes[idx].set_xticks(x)
            axes[idx].set_xticklabels(platforms, rotation=15, ha='right', fontsize=9)
            axes[idx].set_ylabel('Latency (ms - Lower is Better)')
            axes[idx].legend()

        plt.suptitle("Graph Traversal Latency Breakdown (p50 vs p95)", fontsize=14, fontweight='bold', y=1.02)
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "traversal_latencies.png"), bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f"Traversal chart note: {e}")

    # 3. Concurrency Scaling Chart
    try:
        fig, ax = plt.subplots(figsize=(8.5, 5), dpi=300)
        for idx, p in enumerate(platforms):
            conc_data = data[p].get("concurrency", {})
            clients = [v.get("clients") for k, v in conc_data.items() if "clients" in v]
            qps = [v.get("throughput_qps", 0) for k, v in conc_data.items() if "throughput_qps" in v]
            if clients and qps:
                ax.plot(clients, qps, marker='o', linewidth=2.5, label=p, color=colors[idx % len(colors)])

        ax.set_title('Mixed Workload Concurrency Scaling (80% Read / 20% Write)', fontsize=13, fontweight='bold', pad=15)
        ax.set_xlabel('Concurrent Clients (Workers)', fontweight='semibold')
        ax.set_ylabel('Throughput (Queries / Second - Higher is Better)', fontweight='semibold')
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(CHARTS_DIR, "concurrency_scaling.png"))
        plt.close()
    except Exception as e:
        print(f"Concurrency chart note: {e}")

    print(f"Charts saved in: {CHARTS_DIR}")

def generate_markdown_tables(data):
    platforms = list(data.keys())
    if not platforms:
        return ""

    md = "## 📊 Benchmark Results Matrix\n\n"

    # 1. Ingestion Table
    ingest_rows = []
    for p in platforms:
        ing = data[p].get("ingest", {})
        ingest_rows.append([
            p,
            f"{ing.get('total_nodes', 0):,}",
            f"{ing.get('total_edges', 0):,}",
            f"{ing.get('wall_clock_time_s', 0):.2f}s",
            f"{ing.get('nodes_per_sec', 0):,.1f}",
            f"{ing.get('rels_per_sec', 0):,.1f}"
        ])
    md += "### 1. Data Ingestion Performance\n\n"
    md += tabulate(ingest_rows, headers=["Platform", "Nodes Loaded", "Edges Loaded", "Total Wall-Clock Time", "Nodes/sec", "Rels/sec"], tablefmt="github")
    md += "\n\n"

    # 2. Traversals Table
    trav_rows = []
    for p in platforms:
        tr = data[p].get("traversals", {})
        h1 = tr.get("1_hop", {})
        h2 = tr.get("2_hop", {})
        h3 = tr.get("3_hop", {})
        trav_rows.append([
            p,
            f"{h1.get('p50_ms', 0):.2f} / {h1.get('p95_ms', 0):.2f}",
            f"{h2.get('p50_ms', 0):.2f} / {h2.get('p95_ms', 0):.2f}",
            f"{h3.get('p50_ms', 0):.2f} / {h3.get('p95_ms', 0):.2f}"
        ])
    md += "### 2. Traversal Latency (p50 / p95 in ms)\n\n"
    md += tabulate(trav_rows, headers=["Platform", "1-Hop (p50/p95 ms)", "2-Hop (p50/p95 ms)", "3-Hop (p50/p95 ms)"], tablefmt="github")
    md += "\n\n"

    # 3. Lookups & Aggregation Table
    look_rows = []
    for p in platforms:
        lk = data[p].get("lookups", {})
        agg = data[p].get("aggregations", {}).get("aggregation_group_by", {})
        pt = lk.get("point_lookup", {})
        idx = lk.get("indexed_lookup", {})
        look_rows.append([
            p,
            f"{pt.get('p50_ms', 0):.2f} / {pt.get('p95_ms', 0):.2f}",
            f"{idx.get('p50_ms', 0):.2f} / {idx.get('p95_ms', 0):.2f}",
            f"{agg.get('p50_ms', 0):.2f} / {agg.get('p95_ms', 0):.2f}"
        ])
    md += "### 3. Lookups & Aggregations (p50 / p95 in ms)\n\n"
    md += tabulate(look_rows, headers=["Platform", "Point Lookup (p50/p95 ms)", "Indexed Filter Lookup (p50/p95 ms)", "Group-by Aggregation (p50/p95 ms)"], tablefmt="github")
    md += "\n\n"

    # 4. Mixed Concurrency Throughput Table
    conc_rows = []
    for p in platforms:
        c = data[p].get("concurrency", {})
        c1 = c.get("concurrency_1", {})
        c10 = c.get("concurrency_10", {})
        c40 = c.get("concurrency_40", {})
        conc_rows.append([
            p,
            f"{c1.get('throughput_qps', 0):,.1f} QPS (p95: {c1.get('p95_ms', 0):.1f}ms)",
            f"{c10.get('throughput_qps', 0):,.1f} QPS (p95: {c10.get('p95_ms', 0):.1f}ms)",
            f"{c40.get('throughput_qps', 0):,.1f} QPS (p95: {c40.get('p95_ms', 0):.1f}ms)"
        ])
    md += "### 4. Mixed Concurrency Throughput (80% Read / 20% Write)\n\n"
    md += tabulate(conc_rows, headers=["Platform", "1 Client Throughput", "10 Clients Throughput", "40 Clients Throughput"], tablefmt="github")
    md += "\n\n"

    # 5. Resource Footprint Table
    fp_rows = []
    for p in platforms:
        fp = data[p].get("footprint", {})
        fp_rows.append([
            p,
            fp.get("vCPU", "0.5 vCPU"),
            fp.get("RAM_allocated", "256-512 MB"),
            fp.get("memory_usage", "Observable"),
            fp.get("stored_data_size", "Observable")
        ])
    md += "### 5. Hardware Specs & Resource Footprint Parity\n\n"
    md += tabulate(fp_rows, headers=["Platform", "vCPU Allocation", "RAM Allocation", "Memory Behavior", "Storage Representation"], tablefmt="github")
    md += "\n\n"

    with open(SUMMARY_TABLE_PATH, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Summary markdown table saved to: {SUMMARY_TABLE_PATH}")
    return md

def generate_all():
    data = load_metrics()
    if data:
        generate_charts(data)
        generate_markdown_tables(data)

if __name__ == "__main__":
    generate_all()
