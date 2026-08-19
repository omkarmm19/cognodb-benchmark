"""
Metrics Collection and Statistical Analysis
---------------------------------------------
Computes percentile latencies (p50, p90, p95, p99), mean, standard deviation,
throughput (QPS), and error counts across measured query iterations.

All latency values are stored in seconds (from time.perf_counter()) and
converted to milliseconds in the summary output.
"""

import time
import math
from typing import List, Dict, Any


class LatencyTracker:
    """Accumulates per-query latency samples and computes summary statistics."""

    def __init__(self, name: str):
        self.name = name
        self._samples_s: List[float] = []   # raw durations in seconds
        self._start: float = 0.0

    def start(self) -> None:
        self._start = time.perf_counter()

    def record(self, duration_s: float) -> None:
        """Record one query latency in seconds (from time.perf_counter() diff)."""
        self._samples_s.append(duration_s)

    def summary(self, errors: int = 0) -> Dict[str, Any]:
        """
        Returns a statistics dict. Latencies are reported in milliseconds.
        Uses linear interpolation percentiles (consistent with numpy.percentile).
        """
        end = time.perf_counter()
        total_s = end - self._start if self._start > 0 else 0.0
        n = len(self._samples_s)

        if n == 0:
            return {
                "name":             self.name,
                "count":            0,
                "errors":           errors,
                "p50_ms":           None,
                "p90_ms":           None,
                "p95_ms":           None,
                "p99_ms":           None,
                "mean_ms":          None,
                "min_ms":           None,
                "max_ms":           None,
                "std_dev_ms":       None,
                "total_duration_s": round(total_s, 3),
                "throughput_qps":   None,
            }

        sorted_s = sorted(self._samples_s)

        def _percentile(p: float) -> float:
            """Linear interpolation percentile (same as numpy default)."""
            idx = (p / 100.0) * (n - 1)
            lo = int(idx)
            hi = min(lo + 1, n - 1)
            frac = idx - lo
            return sorted_s[lo] + frac * (sorted_s[hi] - sorted_s[lo])

        mean_s = sum(self._samples_s) / n
        variance = sum((x - mean_s) ** 2 for x in self._samples_s) / n

        return {
            "name":             self.name,
            "count":            n,
            "errors":           errors,
            "p50_ms":           round(_percentile(50) * 1000, 3),
            "p90_ms":           round(_percentile(90) * 1000, 3),
            "p95_ms":           round(_percentile(95) * 1000, 3),
            "p99_ms":           round(_percentile(99) * 1000, 3),
            "mean_ms":          round(mean_s * 1000, 3),
            "min_ms":           round(sorted_s[0] * 1000, 3),
            "max_ms":           round(sorted_s[-1] * 1000, 3),
            "std_dev_ms":       round(math.sqrt(variance) * 1000, 3),
            "total_duration_s": round(total_s, 3),
            "throughput_qps":   round(n / total_s, 2) if total_s > 0 else None,
        }
