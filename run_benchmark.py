"""
Master Benchmark Orchestrator CLI
---------------------------------
Automates full benchmarking suite comparing CognoDB Cloud with Neo4j,
Memgraph, FalkorDB, and Kùzu under strict resource parity.

Usage:
  python run_benchmark.py --quick          # Fast smoke-test (5 iterations)
  python run_benchmark.py --full           # Complete 100+ iteration benchmark
  python run_benchmark.py --check          # Test DB connectivity
"""

import os
import sys
import json
import time
import argparse
import random
from dotenv import load_dotenv

# Load environment
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(ENV_PATH)

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
    run_concurrency_sweep
)

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
NODES_CSV = os.path.join(DATA_DIR, "nodes.csv")
EDGES_CSV = os.path.join(DATA_DIR, "edges.csv")

def get_runners():
    return [
        CognoDBRunner(),
        Neo4jRunner(),
        MemgraphRunner(),
        FalkorDBRunner(),
        KuzuRunner()
    ]

def check_connectivity():
    print("=" * 60)
    print("Checking Database Connectivity...")
    print("=" * 60)
    runners = get_runners()
    for r in runners:
        status = "CONNECTED" if r.connect() else "DISCONNECTED / NOT CONFIGURED"
        print(f"  • {r.name:<18} : {status}")
        r.close()
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Graph Database Cloud Benchmarking Suite (Wexa.ai Assessment)")
    parser.add_argument("--check", action="store_true", help="Check connectivity to all configured databases")
    parser.add_argument("--quick", action="store_true", help="Run a quick sanity benchmark with 5 iterations")
    parser.add_argument("--full", action="store_true", help="Run full rigorous benchmark (100+ iterations, concurrency sweeps)")
    parser.add_argument("--iterations", type=int, default=None, help="Custom number of query iterations")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip dataset ingestion step")
    args = parser.parse_args()

    if args.check:
        check_connectivity()
        return

    # Check dataset files
    if not os.path.exists(NODES_CSV) or not os.path.exists(EDGES_CSV):
        print("Dataset CSVs not found. Generating dataset now...")
        import data.download_dataset as dl
        dl.generate_deterministic_dataset()

    iterations = 5 if args.quick else (args.iterations if args.iterations else 100)
    warmup_runs = 5 if args.quick else 20
    concurrency_levels = [1, 5] if args.quick else [1, 10, 40]
    concurrency_duration = 3 if args.quick else 10

    print("=" * 70)
    print("       GRAPH DATABASE CLOUD BENCHMARKING SUITE")
    print(f"       Iterations: {iterations} | Concurrency Sweeps: {concurrency_levels}")
    print("=" * 70)

    # Pick sample node IDs for randomized traversal & lookup tests
    random.seed(1337)
    sample_node_ids = random.sample(range(37700), 200)

    all_results = {}
    runners = get_runners()

    for runner in runners:
        print(f"\n[{runner.name}] Starting benchmark run...")
        is_conn = runner.connect()
        if not is_conn:
            print(f"[{runner.name}] Skipping because database is not connected/reachable.")
            continue

        runner_results = {
            "platform": runner.name,
            "footprint": runner.get_footprint()
        }

        # 1. Clear & Create Schema/Indices
        if not args.skip_ingest:
            print(f"[{runner.name}] Resetting database and creating indices...")
            runner.clear_database()
            runner.create_indices()

            # 2. Ingest Dataset
            print(f"[{runner.name}] Ingesting SNAP GitHub Graph (37.7k nodes, ~394k edges)...")
            ingest_metrics = runner.load_dataset(NODES_CSV, EDGES_CSV, batch_size=1000)
            runner_results["ingest"] = ingest_metrics
            print(f"[{runner.name}] Ingest completed: {ingest_metrics.get('wall_clock_time_s')}s ({ingest_metrics.get('rels_per_sec')} rels/s)")

        # 3. Warm-up
        run_warmup(runner, sample_node_ids, iterations=warmup_runs)

        # 4. Traversals (1-hop, 2-hop, 3-hop)
        print(f"[{runner.name}] Measuring Traversals (1-hop, 2-hop, 3-hop) over {iterations} iterations...")
        runner_results["traversals"] = run_traversal_benchmark(runner, sample_node_ids, iterations=iterations)

        # 5. Lookups (Point & Indexed Filter)
        print(f"[{runner.name}] Measuring Point & Indexed Lookups...")
        runner_results["lookups"] = run_lookup_benchmark(runner, sample_node_ids, iterations=iterations)

        # 6. Aggregations
        print(f"[{runner.name}] Measuring Group-by Aggregations...")
        runner_results["aggregations"] = run_aggregation_benchmark(runner, iterations=iterations)

        # 7. Concurrency Sweeps (1, 10, 40 clients)
        print(f"[{runner.name}] Measuring Mixed Read/Write Concurrency Sweeps ({concurrency_levels})...")
        runner_results["concurrency"] = run_concurrency_sweep(runner, sample_node_ids, concurrency_levels=concurrency_levels, duration_seconds=concurrency_duration)

        all_results[runner.name] = runner_results
        runner.close()

    # Save output JSON
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_file = os.path.join(RESULTS_DIR, "raw_metrics.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 70)
    print(f"Benchmark run complete! Results saved to: {out_file}")
    print("Generating report and charts...")
    print("=" * 70)

    # Automatically generate visualization charts and report
    import generate_report
    generate_report.generate_all()

if __name__ == "__main__":
    main()
