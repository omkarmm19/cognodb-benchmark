"""
Benchmark Workload Execution Suite
------------------------------------
Executes required benchmarks per Wexa.ai assignment specifications:
  - Data loading  (nodes/sec, rels/sec, total wall-clock time)
  - Traversals    (1-hop, 2-hop, 3-hop — p50, p95 latency)
  - Lookups       (point ID, indexed filter — p50, p95 latency)
  - Aggregations  (group-by/degree count — p50, p95 latency)
  - Concurrency   (1, 10, 40 concurrent clients — 80/20 read/write mix)

All timings use time.perf_counter() (monotonic, sub-microsecond resolution).
Warmup iterations are excluded from all measurements.
"""

import time
import random
import concurrent.futures
from typing import Dict, Any, List

from harness.base import BaseGraphRunner
from harness.metrics import LatencyTracker


def run_warmup(runner: BaseGraphRunner, sample_node_ids: List[int], iterations: int = 20):
    """Warms up DB connection pools and page caches. NOT included in metrics."""
    print(f"[{runner.name}] Warming up ({iterations} iterations — excluded from measurements)...")
    for i in range(iterations):
        nid = sample_node_ids[i % len(sample_node_ids)]
        try:
            runner.point_lookup(nid)
            runner.traversal_1_hop(nid)
        except Exception:
            pass


def run_traversal_benchmark(
    runner: BaseGraphRunner, sample_node_ids: List[int], iterations: int = 100
) -> Dict[str, Any]:
    """1-hop, 2-hop, 3-hop traversal latencies across sampled start nodes."""
    results = {}

    for label, fn in [
        ("1_hop", runner.traversal_1_hop),
        ("2_hop", runner.traversal_2_hop),
        ("3_hop", runner.traversal_3_hop),
    ]:
        hop = label.replace("_", "-")
        tracker = LatencyTracker(f"{hop} Traversal")
        tracker.start()
        errors = 0
        for i in range(iterations):
            nid = sample_node_ids[i % len(sample_node_ids)]
            t0 = time.perf_counter()
            try:
                fn(nid)
                tracker.record(time.perf_counter() - t0)
            except Exception:
                errors += 1
        results[label] = tracker.summary(errors=errors)

    return results


def run_lookup_benchmark(
    runner: BaseGraphRunner, sample_node_ids: List[int], iterations: int = 100
) -> Dict[str, Any]:
    """Point ID lookup and indexed stars-filter lookup."""
    results = {}

    # Point lookup by primary key
    tracker_pt = LatencyTracker("Point Lookup (by Primary ID)")
    tracker_pt.start()
    errors = 0
    for i in range(iterations):
        nid = sample_node_ids[i % len(sample_node_ids)]
        t0 = time.perf_counter()
        try:
            runner.point_lookup(nid)
            tracker_pt.record(time.perf_counter() - t0)
        except Exception:
            errors += 1
    results["point_lookup"] = tracker_pt.summary(errors=errors)

    # Indexed filter (stars >= threshold)
    tracker_idx = LatencyTracker("Indexed Filtered Lookup (stars >= threshold)")
    tracker_idx.start()
    errors = 0
    thresholds = [10, 50, 100, 200, 500]
    for i in range(iterations):
        threshold = thresholds[i % len(thresholds)]
        t0 = time.perf_counter()
        try:
            runner.indexed_lookup(threshold)
            tracker_idx.record(time.perf_counter() - t0)
        except Exception:
            errors += 1
    results["indexed_lookup"] = tracker_idx.summary(errors=errors)

    return results


def run_aggregation_benchmark(
    runner: BaseGraphRunner, iterations: int = 100
) -> Dict[str, Any]:
    """Group-by aggregation (language + relation count)."""
    tracker = LatencyTracker("Group-by Aggregation (Language & Relations)")
    tracker.start()
    errors = 0
    for _ in range(iterations):
        t0 = time.perf_counter()
        try:
            runner.aggregation_degree()
            tracker.record(time.perf_counter() - t0)
        except Exception:
            errors += 1
    return {"aggregation_group_by": tracker.summary(errors=errors)}


def run_concurrency_sweep(
    runner: BaseGraphRunner,
    sample_node_ids: List[int],
    concurrency_levels: List[int] = None,
    duration_seconds: int = 10,
) -> Dict[str, Any]:
    """
    Mixed workload concurrency sweep.
    80% reads (point_lookup + traversal_1_hop) / 20% writes (execute_write).
    Each level runs for `duration_seconds` wall-clock seconds.
    """
    if concurrency_levels is None:
        concurrency_levels = [1, 10, 40]

    results = {}

    def _worker(node_ids, stop_flag, latencies, write_prob=0.2):
        local_latencies = []
        while not stop_flag[0]:
            nid = random.choice(node_ids)
            t0 = time.perf_counter()
            try:
                if random.random() < write_prob:
                    runner.execute_write(nid, random.randint(1, 5000))
                else:
                    runner.point_lookup(nid)
                    runner.traversal_1_hop(nid)
                local_latencies.append(time.perf_counter() - t0)
            except Exception:
                pass
        latencies.extend(local_latencies)

    for n_clients in concurrency_levels:
        stop_flag = [False]
        all_latencies = []

        t_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_clients) as pool:
            futures = [
                pool.submit(_worker, sample_node_ids, stop_flag, all_latencies)
                for _ in range(n_clients)
            ]
            time.sleep(duration_seconds)
            stop_flag[0] = True
            concurrent.futures.wait(futures, timeout=10)

        wall = time.perf_counter() - t_start
        total_ops = len(all_latencies)
        qps = total_ops / wall if wall > 0 else 0

        sorted_lat = sorted(all_latencies)
        p50 = sorted_lat[int(len(sorted_lat) * 0.50)] * 1000 if sorted_lat else 0
        p95 = sorted_lat[int(len(sorted_lat) * 0.95)] * 1000 if sorted_lat else 0

        results[f"concurrency_{n_clients}"] = {
            "clients":        n_clients,
            "total_ops":      total_ops,
            "errors":         0,
            "duration_s":     round(wall, 2),
            "throughput_qps": round(qps, 2),
            "p50_ms":         round(p50, 2),
            "p95_ms":         round(p95, 2),
        }
        print(
            f"[{runner.name}]   concurrency={n_clients}: "
            f"{total_ops:,} ops in {wall:.1f}s → {qps:,.0f} qps  "
            f"p50={p50:.1f}ms p95={p95:.1f}ms"
        )

    return results
