"""
Benchmark Workload Execution Suite
----------------------------------
Executes required benchmarks per Wexa.ai specifications (Section 5.2):
- Data loading (Nodes/sec, Rels/sec, Total wall-clock time)
- Traversals (1-hop, 2-hop, 3-hop latency percentiles p50, p95)
- Lookups (Point ID and Indexed filter p50, p95)
- Aggregations (Group-by/degree count p50, p95)
- Mixed Workload (1, 10, 40 concurrent clients, 80/20 Read/Write mix)
"""

import time
import random
import concurrent.futures
from typing import Dict, Any, List
from harness.base import BaseGraphRunner
from harness.metrics import LatencyTracker

def run_warmup(runner: BaseGraphRunner, sample_node_ids: List[int], iterations: int = 20):
    """Warms up database caches and connection pools before measuring."""
    print(f"[{runner.name}] Warming up database caches ({iterations} iterations)...")
    for _ in range(iterations):
        nid = random.choice(sample_node_ids)
        try:
            runner.point_lookup(nid)
            runner.traversal_1_hop(nid)
        except Exception:
            pass

def run_traversal_benchmark(runner: BaseGraphRunner, sample_node_ids: List[int], iterations: int = 100) -> Dict[str, Any]:
    """Runs 1-hop, 2-hop, and 3-hop graph traversals across sample nodes."""
    results = {}
    
    # 1-Hop
    tracker_1 = LatencyTracker("1-hop Traversal")
    tracker_1.start()
    for i in range(iterations):
        nid = sample_node_ids[i % len(sample_node_ids)]
        t0 = time.perf_counter()
        try:
            runner.traversal_1_hop(nid)
            tracker_1.record((time.perf_counter() - t0) * 1000.0)
        except Exception as e:
            tracker_1.record_error()
    tracker_1.finish()
    results["1_hop"] = tracker_1.get_summary()

    # 2-Hop
    tracker_2 = LatencyTracker("2-hop Traversal")
    tracker_2.start()
    for i in range(iterations):
        nid = sample_node_ids[i % len(sample_node_ids)]
        t0 = time.perf_counter()
        try:
            runner.traversal_2_hop(nid)
            tracker_2.record((time.perf_counter() - t0) * 1000.0)
        except Exception as e:
            tracker_2.record_error()
    tracker_2.finish()
    results["2_hop"] = tracker_2.get_summary()

    # 3-Hop (Capped/Sampled to prevent runaway memory on deep paths)
    tracker_3 = LatencyTracker("3-hop Traversal")
    tracker_3.start()
    for i in range(iterations):
        nid = sample_node_ids[i % len(sample_node_ids)]
        t0 = time.perf_counter()
        try:
            runner.traversal_3_hop(nid)
            tracker_3.record((time.perf_counter() - t0) * 1000.0)
        except Exception as e:
            tracker_3.record_error()
    tracker_3.finish()
    results["3_hop"] = tracker_3.get_summary()

    return results

def run_lookup_benchmark(runner: BaseGraphRunner, sample_node_ids: List[int], iterations: int = 100) -> Dict[str, Any]:
    """Measures Point lookup (by ID) and Indexed property lookup (stars >= threshold)."""
    # 1. Point Lookup
    tracker_point = LatencyTracker("Point Lookup (by Primary ID)")
    tracker_point.start()
    for i in range(iterations):
        nid = sample_node_ids[i % len(sample_node_ids)]
        t0 = time.perf_counter()
        try:
            runner.point_lookup(nid)
            tracker_point.record((time.perf_counter() - t0) * 1000.0)
        except Exception:
            tracker_point.record_error()
    tracker_point.finish()

    # 2. Indexed / Filtered Lookup
    tracker_indexed = LatencyTracker("Indexed Filtered Lookup (stars >= threshold)")
    tracker_indexed.start()
    for _ in range(iterations):
        stars_threshold = random.randint(10, 50)
        t0 = time.perf_counter()
        try:
            runner.indexed_lookup(stars_threshold)
            tracker_indexed.record((time.perf_counter() - t0) * 1000.0)
        except Exception:
            tracker_indexed.record_error()
    tracker_indexed.finish()

    return {
        "point_lookup": tracker_point.get_summary(),
        "indexed_lookup": tracker_indexed.get_summary()
    }

def run_aggregation_benchmark(runner: BaseGraphRunner, iterations: int = 100) -> Dict[str, Any]:
    """Measures Group-by / count aggregation performance."""
    tracker = LatencyTracker("Group-by Aggregation (Language & Relations)")
    tracker.start()
    for _ in range(iterations):
        t0 = time.perf_counter()
        try:
            runner.aggregation_degree()
            tracker.record((time.perf_counter() - t0) * 1000.0)
        except Exception:
            tracker.record_error()
    tracker.finish()

    return {
        "aggregation_group_by": tracker.get_summary()
    }

def run_concurrency_sweep(runner: BaseGraphRunner, sample_node_ids: List[int], concurrency_levels: List[int] = [1, 10, 40], duration_seconds: int = 10) -> Dict[str, Any]:
    """
    Executes mixed Read (80%) / Write (20%) workloads under concurrent client threads.
    Measures sustained QPS and p50/p95 latency under concurrency contention.
    """
    sweep_results = {}

    for clients in concurrency_levels:
        print(f"[{runner.name}] Running Mixed Concurrency Sweep: {clients} clients ({duration_seconds}s)...")
        latencies = []
        errors = 0
        end_time = time.perf_counter() + duration_seconds
        
        def worker():
            nonlocal errors
            local_latencies = []
            while time.perf_counter() < end_time:
                nid = random.choice(sample_node_ids)
                is_write = random.random() < 0.20
                t0 = time.perf_counter()
                try:
                    if is_write:
                        runner.execute_write(nid, random.randint(1, 500))
                    else:
                        runner.traversal_1_hop(nid)
                    local_latencies.append((time.perf_counter() - t0) * 1000.0)
                except Exception:
                    errors += 1
            return local_latencies

        t_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as executor:
            futures = [executor.submit(worker) for _ in range(clients)]
            for f in concurrent.futures.as_completed(futures):
                try:
                    latencies.extend(f.result())
                except Exception:
                    errors += 1
        t_total = time.perf_counter() - t_start

        import numpy as np
        if latencies:
            arr = np.array(latencies)
            qps = round(len(arr) / t_total, 2)
            p50 = round(float(np.percentile(arr, 50)), 2)
            p95 = round(float(np.percentile(arr, 95)), 2)
        else:
            qps, p50, p95 = 0.0, 0.0, 0.0

        sweep_results[f"concurrency_{clients}"] = {
            "clients": clients,
            "total_ops": len(latencies),
            "errors": errors,
            "duration_s": round(t_total, 2),
            "throughput_qps": qps,
            "p50_ms": p50,
            "p95_ms": p95
        }

    return sweep_results
