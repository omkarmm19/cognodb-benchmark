"""
Kùzu Benchmark Runner (Native Vectorized Columnar Engine)
---------------------------------------------------------
Kùzu is an in-process, vectorized columnar graph database management system.
Designed for OLAP graph query processing with query execution modeled after
state-of-the-art columnar RDBMSs.

Resource configuration:
  - Buffer Pool Size: 512 MB (configured to match CognoDB memory parity)
  - Execution Threads: 1 (capped to match 0.5 - 1 vCPU single core baseline)
  - Deployment: Embedded (in-process)
"""

import os
import time
import shutil
from typing import Dict, Any, List, Optional
from harness.base import BaseGraphRunner


class KuzuRunner(BaseGraphRunner):
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("Kùzu", config or {})
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.db_path = os.path.join(root_dir, "data_kuzu_db")
        self.db = None
        self.conn = None

    def connect(self) -> bool:
        try:
            import kuzu
            buffer_pool_size = 512 * 1024 * 1024
            print(f"[{self.name}] Initializing native Kùzu embedded database at '{self.db_path}' (512 MB buffer pool, 1 worker thread)...")
            self.db = kuzu.Database(self.db_path, buffer_pool_size=buffer_pool_size)
            self.conn = kuzu.Connection(self.db, num_threads=1)
            self.connected = True
            print(f"[{self.name}] Native Kùzu engine initialized successfully (kuzu v{kuzu.__version__}).")
            return True
        except Exception as e:
            print(f"[{self.name}] Failed to initialize native Kùzu: {e}")
            self.connected = False
            return False

    def close(self):
        self.conn = None
        self.db = None
        self.connected = False

    def clear_database(self) -> bool:
        if not self.connected or not self.conn:
            return False
        try:
            try:
                self.conn.execute("DROP TABLE IF EXISTS FOLLOWS")
                self.conn.execute("DROP TABLE IF EXISTS Developer")
            except Exception:
                pass
            print(f"[{self.name}] Database schema cleared.")
            return True
        except Exception as e:
            print(f"[{self.name}] Warning clearing db: {e}")
            return False

    def create_indices(self) -> bool:
        if not self.connected or not self.conn:
            return False
        try:
            self.conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS Developer(
                    node_id INT64,
                    name STRING,
                    stars INT64,
                    repos INT64,
                    language STRING,
                    created_year INT64,
                    PRIMARY KEY (node_id)
                )
            """)
            self.conn.execute("""
                CREATE REL TABLE IF NOT EXISTS FOLLOWS(
                    FROM Developer TO Developer,
                    rel_type STRING,
                    weight DOUBLE
                )
            """)
            print(f"[{self.name}] Schema & primary key indices created.")
            return True
        except Exception as e:
            print(f"[{self.name}] Schema creation notice: {e}")
            return False

    def load_dataset(self, nodes_csv: str, edges_csv: str, batch_size: int = 1000) -> Dict[str, Any]:
        """Loads dataset using Kùzu's vectorized bulk CSV copy."""
        t_start = time.perf_counter()
        
        abs_nodes_path = os.path.abspath(nodes_csv)
        abs_edges_path = os.path.abspath(edges_csv)

        print(f"[{self.name}] Ingesting nodes via vectorized COPY FROM '{abs_nodes_path}'...")
        self.conn.execute(f"COPY Developer FROM '{abs_nodes_path}' (HEADER=true)")
        
        node_res = self.conn.execute("MATCH (d:Developer) RETURN count(d)").get_next()
        total_nodes = int(node_res[0])
        print(f"[{self.name}] Nodes ingested: {total_nodes:,}")

        print(f"[{self.name}] Ingesting relationships via vectorized COPY FROM '{abs_edges_path}'...")
        self.conn.execute(f"COPY FOLLOWS FROM '{abs_edges_path}' (HEADER=true)")
        
        edge_res = self.conn.execute("MATCH ()-[r:FOLLOWS]->() RETURN count(r)").get_next()
        total_edges = int(edge_res[0])
        print(f"[{self.name}] Relationships ingested: {total_edges:,}")

        t_total = time.perf_counter() - t_start
        return {
            "platform": self.name,
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "wall_clock_time_s": round(t_total, 3),
            "nodes_per_sec": round(total_nodes / t_total, 2) if t_total > 0 else 0,
            "rels_per_sec": round(total_edges / t_total, 2) if t_total > 0 else 0
        }

    def point_lookup(self, node_id: int) -> Optional[Any]:
        res = self.conn.execute(
            f"MATCH (d:Developer) WHERE d.node_id = {node_id} RETURN d.name, d.stars, d.language LIMIT 1"
        )
        return res.get_next() if res.has_next() else None

    def indexed_lookup(self, min_stars: int) -> List[Any]:
        res = self.conn.execute(
            f"MATCH (d:Developer) WHERE d.stars >= {min_stars} RETURN d.node_id, d.stars, d.language LIMIT 50"
        )
        out = []
        while res.has_next():
            out.append(res.get_next())
        return out

    def traversal_1_hop(self, node_id: int) -> int:
        res = self.conn.execute(
            f"MATCH (d:Developer)-[:FOLLOWS]->(n:Developer) WHERE d.node_id = {node_id} RETURN count(n)"
        )
        return res.get_next()[0] if res.has_next() else 0

    def traversal_2_hop(self, node_id: int) -> int:
        res = self.conn.execute(
            f"MATCH (d:Developer)-[:FOLLOWS*2..2]->(n:Developer) WHERE d.node_id = {node_id} RETURN count(DISTINCT n)"
        )
        return res.get_next()[0] if res.has_next() else 0

    def traversal_3_hop(self, node_id: int) -> int:
        res = self.conn.execute(
            f"MATCH (d:Developer)-[:FOLLOWS*3..3]->(n:Developer) WHERE d.node_id = {node_id} RETURN count(DISTINCT n)"
        )
        return res.get_next()[0] if res.has_next() else 0

    def aggregation_degree(self) -> List[Any]:
        res = self.conn.execute("""
            MATCH (d:Developer)-[r:FOLLOWS]->()
            RETURN d.language, count(r) AS rels, avg(d.stars) AS avg_stars
            ORDER BY rels DESC
            LIMIT 10
        """)
        out = []
        while res.has_next():
            out.append(res.get_next())
        return out

    def execute_write(self, node_id: int, new_stars: int) -> bool:
        self.conn.execute(f"MATCH (d:Developer) WHERE d.node_id = {node_id} SET d.stars = {new_stars}")
        return True

    def get_footprint(self) -> Dict[str, Any]:
        import kuzu
        return {
            "deployment": "Embedded In-Process (Vectorized Columnar OLAP)",
            "vCPU": "1 worker thread (configured via num_threads=1)",
            "RAM_allocated_MB": 512,
            "buffer_pool_size": "512 MB (explicitly configured)",
            "storage": "Columnar CSR / on-disk vectorized files",
            "memory_usage": "Bounded by 512 MB buffer pool",
            "kuzu_version": kuzu.__version__,
            "note": "Embedded in-process engine. Zero network serialization/RTT overhead."
        }
