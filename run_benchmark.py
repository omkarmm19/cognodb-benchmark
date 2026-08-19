"""
Master Benchmark Orchestrator
------------------------------
Runs the complete benchmark suite across all configured graph databases.

Usage:
  python run_benchmark.py --check         # Test connectivity only
  python run_benchmark.py --quick         # 20 warmup + 20 measured iterations (smoke test)
  python run_benchmark.py --full          # 20 warmup + 100+ measured iterations (final submission)
  python run_benchmark.py --skip-ingest   # Re-run workloads without re-loading data

IMPORTANT: Only databases that successfully connect are benchmarked.
           Databases that fail to connect are recorded as "unavailable"
           in the results — no simulated or fake numbers are produced.

Required environment variables (set in .env — never commit this file):
  COGNODB_URI, COGNODB_USER, COGNODB_PASSWORD
  NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD  (optional: skip if not configured)
  MEMGRAPH_URI                           (optional: skip if not configured)
  FALKORDB_HOST                          (optional: skip if not configured)
"""

import os
import sys
import json
import time
import argparse
import random
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from harness.runners.cognodb_runner import CognoDBRunner
from harness.runners.neo4j_runner import Neo4jRunner
from harness.runners.memgraph_runner import MemgraphRunner
from harness.runners.falkordb_runner import FalkorDBRunner
from harness.runners.kuzu_runner import KuzuRunner
from harness.workloads import (
    run_warmup,
    run_traversal_benchmark,
    run_lookup_benchmark,
    run_aggregation_benchmark,
    run_concurrency_sweep,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(ROOT, "results")
NODES_CSV = os.path.join(ROOT, "data", "nodes.csv")
EDGES_CSV = os.path.join(ROOT, "data", "edges.csv")


# ── Runner registry ──────────────────────────────────────────────────────────

def get_runners():
    return [
        CognoDBRunner(),
        Neo4jRunner(),
        MemgraphRunner(),
        FalkorDBRunner(),
        KuzuRunner(),
    ]


# ── Connectivity check ───────────────────────────────────────────────────────

def check_connectivity():
    print("=" * 64)
    print("  Connectivity check")
    print("=" * 64)
    for r in get_runners():
        ok = r.connect()
        status = "✓  CONNECTED" if ok else "✗  UNAVAILABLE"
        print(f"  {r.name:<22} {status}")
        r.close()
    print("=" * 64)


# ── Main orchestrator ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Graph DB Cloud Benchmark Suite — Wexa.ai")
    parser.add_argument("--check",       action="store_true", help="Connectivity check only")
    parser.add_argument("--quick",       action="store_true", help="Quick smoke test (20 warmup + 20 measured)")
    parser.add_argument("--full",        action="store_true", help="Full benchmark (20 warmup + 100 measured)")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip dataset ingestion")
    args = parser.parse_args()

    if args.check:
        check_connectivity()
        return

    # Ensure dataset is present
    if not os.path.exists(NODES_CSV) or not os.path.exists(EDGES_CSV):
        print("Dataset CSVs missing — run: python data/download_dataset.py")
        sys.exit(1)

    # Benchmark parameters
    if args.quick:
        warmup_iters       = 20
        measured_iters     = 20
        concurrency_levels = [1, 10]
        conc_duration_s    = 5
    else:  # --full (default)
        warmup_iters       = 20
        measured_iters     = 100
        concurrency_levels = [1, 10, 40]
        conc_duration_s    = 10

    print("=" * 64)
    print(f"  Graph DB Cloud Benchmark Suite — {'QUICK' if args.quick else 'FULL'} RUN")
    print(f"  Warmup: {warmup_iters}   Measured: {measured_iters}   Concurrency: {concurrency_levels}")
    print(f"  Dataset: {NODES_CSV}")
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 64)

    # Fixed random seed for reproducible node sampling
    random.seed(42)
    sample_node_ids = random.sample(range(37700), 200)

    all_results = {}
    skipped = []

    for runner in get_runners():
        print(f"\n{'─'*64}")
        print(f"  Database: {runner.name}")
        print(f"{'─'*64}")

        if not runner.connect():
            skipped.append(runner.name)
            all_results[runner.name] = {
                "platform": runner.name,
                "status":   "unavailable",
                "reason":   "Connection failed or credentials not configured",
                "footprint": runner.get_footprint(),
            }
            runner.close()
            continue

        result = {
            "platform":  runner.name,
            "status":    "ok",
            "footprint": runner.get_footprint(),
        }

        # ── 1. Ingest ─────────────────────────────────────────────────────
        if not args.skip_ingest:
            print(f"[{runner.name}] Clearing database and creating indices...")
            runner.clear_database()
            runner.create_indices()
            print(f"[{runner.name}] Loading dataset (identical for all runners)...")
            ingest = runner.load_dataset(NODES_CSV, EDGES_CSV)
            result["ingest"] = ingest
            print(
                f"[{runner.name}] Ingest done: {ingest.get('total_nodes',0):,} nodes, "
                f"{ingest.get('total_edges',0):,} edges in {ingest.get('wall_clock_time_s',0):.1f}s "
                f"({ingest.get('rels_per_sec',0):,.0f} rels/s)"
            )
        else:
            result["ingest"] = {"note": "Skipped (--skip-ingest flag)"}

        # ── 2. Warm-up (NOT included in measurements) ─────────────────────
        print(f"[{runner.name}] Warming up ({warmup_iters} iterations, not measured)...")
        run_warmup(runner, sample_node_ids, iterations=warmup_iters)

        # ── 3. Traversals ─────────────────────────────────────────────────
        print(f"[{runner.name}] Traversals (1/2/3-hop) — {measured_iters} measured iterations...")
        result["traversals"] = run_traversal_benchmark(
            runner, sample_node_ids, iterations=measured_iters
        )

        # ── 4. Lookups ────────────────────────────────────────────────────
        print(f"[{runner.name}] Lookups (point + indexed) — {measured_iters} iterations...")
        result["lookups"] = run_lookup_benchmark(
            runner, sample_node_ids, iterations=measured_iters
        )

        # ── 5. Aggregation ────────────────────────────────────────────────
        print(f"[{runner.name}] Aggregation — {measured_iters} iterations...")
        result["aggregations"] = run_aggregation_benchmark(runner, iterations=measured_iters)

        # ── 6. Mixed concurrency ──────────────────────────────────────────
        print(f"[{runner.name}] Mixed concurrency sweep {concurrency_levels} × {conc_duration_s}s...")
        result["concurrency"] = run_concurrency_sweep(
            runner,
            sample_node_ids,
            concurrency_levels=concurrency_levels,
            duration_seconds=conc_duration_s,
        )

        all_results[runner.name] = result
        runner.close()

    # ── Save raw results ──────────────────────────────────────────────────────
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_file = os.path.join(RESULTS_DIR, "raw_metrics.json")
    meta = {
        "__meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode":         "quick" if args.quick else "full",
            "warmup_iters": warmup_iters,
            "measured_iters": measured_iters,
            "concurrency_levels": concurrency_levels,
            "dataset_nodes": 37700,
            "dataset_edges": 394213,
            "dataset_source": "SNAP GitHub Social Network (musae-github) — deterministic generation",
            "random_seed":  42,
        }
    }
    meta.update(all_results)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print(f"\n{'='*64}")
    print(f"  Benchmark complete.")
    print(f"  Results saved to: {out_file}")
    if skipped:
        print(f"  Skipped (unavailable): {', '.join(skipped)}")
    print(f"{'='*64}\n")

    # Auto-generate charts and summary table
    print("Generating charts and summary table...")
    import generate_report
    generate_report.generate_all()


if __name__ == "__main__":
    main()
