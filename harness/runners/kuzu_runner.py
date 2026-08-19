"""
Kùzu Benchmark Runner
----------------------
Kùzu is an embedded, vectorized columnar graph database engine.
It requires the `kuzu` Python package, which must be compiled from source
and currently does not have a prebuilt wheel for Python 3.14 (arm64).

Status on this machine:
  Python version: 3.14.2 (arm64, macOS)
  kuzu 0.11.3 install: FAILED — no prebuilt wheel, source build fails.
  Result: Kùzu benchmark is UNAVAILABLE on this environment.

This runner will always return connected=False with a clear explanation.
No simulated or fallback data is produced.

To reproduce Kùzu results:
  1. Use Python 3.10, 3.11, or 3.12 (prebuilt wheels available)
  2. pip install kuzu
  3. Run: python run_benchmark.py --full

Design notes (for reference if Kùzu becomes available):
  - Uses COPY FROM for bulk ingest (vectorized CSV reader)
  - Cypher queries identical to other runners
  - Schema: CREATE NODE TABLE Developer(..., PRIMARY KEY (node_id))
             CREATE REL TABLE FOLLOWS(FROM Developer TO Developer, weight DOUBLE)
  - Resource cap: buffer_pool_size=512MB, num_threads=1
"""

from typing import Dict, Any, List, Optional
from harness.base import BaseGraphRunner


class KuzuRunner(BaseGraphRunner):
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("Kùzu", config or {})

    def connect(self) -> bool:
        try:
            import kuzu  # noqa: F401
        except ImportError:
            print(
                f"[{self.name}] kuzu package not available for Python 3.14 (no prebuilt wheel). "
                f"Benchmark unavailable. See harness/runners/kuzu_runner.py for details."
            )
            self.connected = False
            return False

        print(f"[{self.name}] kuzu available — would initialize embedded DB here.")
        self.connected = False  # placeholder; full implementation requires Python ≤3.12
        return False

    def close(self): pass
    def clear_database(self) -> bool: return False
    def create_indices(self) -> bool: return False

    def load_dataset(self, nodes_csv, edges_csv, batch_size=1000) -> Dict[str, Any]:
        return {"platform": self.name, "status": "unavailable"}

    def point_lookup(self, node_id: int) -> Optional[Any]: return None
    def indexed_lookup(self, min_stars: int) -> List[Any]: return []
    def traversal_1_hop(self, node_id: int) -> int: return 0
    def traversal_2_hop(self, node_id: int) -> int: return 0
    def traversal_3_hop(self, node_id: int) -> int: return 0
    def aggregation_degree(self) -> List[Any]: return []
    def execute_write(self, node_id: int, new_stars: int) -> bool: return False

    def get_footprint(self) -> Dict[str, Any]:
        return {
            "deployment":   "Embedded (would run in-process on benchmark client machine)",
            "status":       "Unavailable — kuzu has no prebuilt wheel for Python 3.14 arm64",
            "workaround":   "Re-run with Python 3.10/3.11/3.12 to enable Kùzu benchmark",
        }
