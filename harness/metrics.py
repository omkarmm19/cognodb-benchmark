"""
Metrics Collection and Statistical Analysis Module
--------------------------------------------------
Computes percentile latencies (p50, p90, p95, p99), mean, throughput (QPS),
and error statistics across query iterations.
"""

import numpy as np
import time
from typing import List, Dict, Any

class LatencyTracker:
    def __init__(self, name: str):
        self.name = name
        self.latencies_ms: List[float] = []
        self.errors: int = 0
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def start(self):
        self.start_time = time.perf_counter()

    def record(self, duration_ms: float):
        self.latencies_ms.append(duration_ms)

    def record_error(self):
        self.errors += 1

    def finish(self):
        self.end_time = time.perf_counter()

    def get_summary(self) -> Dict[str, Any]:
        if not self.latencies_ms:
            return {
                "name": self.name,
                "count": 0,
                "errors": self.errors,
                "p50_ms": 0.0,
                "p90_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "mean_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "std_dev_ms": 0.0,
                "total_duration_s": round(self.end_time - self.start_time, 3) if self.end_time > self.start_time else 0.0,
                "throughput_qps": 0.0
            }

        arr = np.array(self.latencies_ms)
        total_time = self.end_time - self.start_time
        qps = round(len(arr) / total_time, 2) if total_time > 0 else 0.0

        return {
            "name": self.name,
            "count": len(arr),
            "errors": self.errors,
            "p50_ms": round(float(np.percentile(arr, 50)), 2),
            "p90_ms": round(float(np.percentile(arr, 90)), 2),
            "p95_ms": round(float(np.percentile(arr, 95)), 2),
            "p99_ms": round(float(np.percentile(arr, 99)), 2),
            "mean_ms": round(float(np.mean(arr)), 2),
            "min_ms": round(float(np.min(arr)), 2),
            "max_ms": round(float(np.max(arr)), 2),
            "std_dev_ms": round(float(np.std(arr)), 2),
            "total_duration_s": round(total_time, 3),
            "throughput_qps": qps
        }
