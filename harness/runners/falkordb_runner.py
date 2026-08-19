"""
FalkorDB Benchmark Runner
--------------------------
Connects to FalkorDB using the official falkordb Python client.
FalkorDB is a low-latency graph database backed by Redis and GraphBLAS
sparse adjacency matrices.

Target:
  - Local Docker container on port 6379 (falkordb/falkordb:latest)
  - Enforced resource limits: 0.5 vCPU, 512 MB RAM (matching CognoDB parity)
"""

import os
import csv
import time
from typing import Dict, Any, List, Optional

from harness.base import BaseGraphRunner


class FalkorDBRunner(BaseGraphRunner):
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("FalkorDB", config or {})
        self.host = self.config.get("FALKORDB_HOST") or os.getenv("FALKORDB_HOST", "localhost")
        self.port = int(self.config.get("FALKORDB_PORT") or os.getenv("FALKORDB_PORT", 6379))
        self.password = self.config.get("FALKORDB_PASSWORD") or os.getenv("FALKORDB_PASSWORD", "")
        self.graph = None
        self._client = None

    def connect(self) -> bool:
        if not self.host:
            print(f"[{self.name}] FALKORDB_HOST not set in .env — skipping.")
            return False
        try:
            from falkordb import FalkorDB
            print(f"[{self.name}] Connecting to {self.host}:{self.port}...")
            self._client = FalkorDB(
                host=self.host,
                port=self.port,
                password=self.password if self.password else None,
            )
            self.graph = self._client.select_graph("benchmark_social")
            self.graph.query("RETURN 1")
            self.connected = True
            print(f"[{self.name}] Connected successfully.")
            return True
        except Exception as e:
            print(f"[{self.name}] Connection failed: {e}")
            self.connected = False
            return False

    def close(self):
        self.connected = False
        self.graph = None
        self._client = None

    def clear_database(self) -> bool:
        if not self.graph:
            return False
        try:
            self.graph.delete()
            self.graph = self._client.select_graph("benchmark_social")
            print(f"[{self.name}] Database cleared.")
            return True
        except Exception as e:
            print(f"[{self.name}] Warning clearing db: {e}")
            return False

    def create_indices(self) -> bool:
        if not self.graph:
            return False
        try:
            try:
                self.graph.query("CREATE INDEX FOR (d:Developer) ON (d.node_id)")
            except Exception:
                pass
            try:
                self.graph.query("CREATE INDEX FOR (d:Developer) ON (d.stars)")
            except Exception:
                pass
            print(f"[{self.name}] Indices created: Developer(node_id), Developer(stars).")
            return True
        except Exception as e:
            print(f"[{self.name}] Index creation notice: {e}")
            return False

    def load_dataset(
        self, nodes_csv: str, edges_csv: str, batch_size: int = 2000
    ) -> Dict[str, Any]:
        t_start = time.perf_counter()
        total_nodes = 0
        total_edges = 0

        # Ingest Nodes
        print(f"[{self.name}] Ingesting nodes (batch_size={batch_size})...")
        with open(nodes_csv, "r", encoding="utf-8") as f:
            batch: List[Dict[str, Any]] = []
            for row in csv.DictReader(f):
                batch.append({
                    "node_id":      int(row["node_id"]),
                    "name":         row["name"],
                    "stars":        int(row["stars"]),
                    "repos":        int(row["repos"]),
                    "language":     row["language"],
                    "created_year": int(row["created_year"]),
                })
                if len(batch) >= batch_size:
                    self._insert_nodes(batch)
                    total_nodes += len(batch)
                    print(f"[{self.name}]   nodes: {total_nodes:,}", end="\r")
                    batch = []
            if batch:
                self._insert_nodes(batch)
                total_nodes += len(batch)
        print(f"\n[{self.name}] Nodes ingested: {total_nodes:,}")

        # Ingest Edges
        print(f"[{self.name}] Ingesting relationships (batch_size={batch_size})...")
        with open(edges_csv, "r", encoding="utf-8") as f:
            batch = []
            for row in csv.DictReader(f):
                batch.append({
                    "source_id": int(row["source_id"]),
                    "target_id": int(row["target_id"]),
                    "weight":    float(row["weight"]),
                })
                if len(batch) >= batch_size:
                    self._insert_edges(batch)
                    total_edges += len(batch)
                    print(f"[{self.name}]   edges: {total_edges:,}", end="\r")
                    batch = []
            if batch:
                self._insert_edges(batch)
                total_edges += len(batch)
        print(f"\n[{self.name}] Edges ingested: {total_edges:,}")

        # Verify counts in graph
        n_res = self.graph.query("MATCH (d:Developer) RETURN count(d)").result_set
        n_count = n_res[0][0] if n_res else total_nodes
        r_res = self.graph.query("MATCH ()-[r:FOLLOWS]->() RETURN count(r)").result_set
        r_count = r_res[0][0] if r_res else total_edges

        t_total = time.perf_counter() - t_start
        return {
            "platform":          self.name,
            "total_nodes":       n_count,
            "total_edges":       r_count,
            "wall_clock_time_s": round(t_total, 2),
            "nodes_per_sec":     round(total_nodes / t_total, 2) if t_total > 0 else 0,
            "rels_per_sec":      round(total_edges / t_total, 2) if t_total > 0 else 0,
        }

    def _insert_nodes(self, batch: List[Dict[str, Any]]) -> None:
        query = """
        UNWIND $batch AS row
        CREATE (d:Developer {
            node_id:      row.node_id,
            name:         row.name,
            stars:        row.stars,
            repos:        row.repos,
            language:     row.language,
            created_year: row.created_year
        })
        """
        self.graph.query(query, {"batch": batch})

    def _insert_edges(self, batch: List[Dict[str, Any]]) -> None:
        query = """
        UNWIND $batch AS row
        MATCH (a:Developer {node_id: row.source_id})
        MATCH (b:Developer {node_id: row.target_id})
        CREATE (a)-[:FOLLOWS {weight: row.weight}]->(b)
        """
        self.graph.query(query, {"batch": batch})

    def point_lookup(self, node_id: int) -> Optional[Any]:
        res = self.graph.query(
            "MATCH (d:Developer {node_id: $id}) RETURN d.name, d.stars, d.language LIMIT 1",
            {"id": node_id},
        )
        return res.result_set[0] if res.result_set else None

    def indexed_lookup(self, min_stars: int) -> List[Any]:
        res = self.graph.query(
            "MATCH (d:Developer) WHERE d.stars >= $stars RETURN d.node_id, d.stars LIMIT 50",
            {"stars": min_stars},
        )
        return res.result_set

    def traversal_1_hop(self, node_id: int) -> int:
        res = self.graph.query(
            "MATCH (d:Developer {node_id: $id})-[:FOLLOWS]->(n) RETURN count(n) AS cnt",
            {"id": node_id},
        )
        return res.result_set[0][0] if res.result_set else 0

    def traversal_2_hop(self, node_id: int) -> int:
        res = self.graph.query(
            "MATCH (d:Developer {node_id: $id})-[:FOLLOWS*2]->(n) RETURN count(DISTINCT n) AS cnt",
            {"id": node_id},
        )
        return res.result_set[0][0] if res.result_set else 0

    def traversal_3_hop(self, node_id: int) -> int:
        res = self.graph.query(
            "MATCH (d:Developer {node_id: $id})-[:FOLLOWS*3]->(n) RETURN count(DISTINCT n) AS cnt",
            {"id": node_id},
        )
        return res.result_set[0][0] if res.result_set else 0

    def aggregation_degree(self) -> List[Any]:
        res = self.graph.query(
            "MATCH (d:Developer)-[r:FOLLOWS]->() "
            "RETURN d.language AS lang, count(r) AS rels, avg(d.stars) AS avg_stars "
            "ORDER BY rels DESC LIMIT 10"
        )
        return res.result_set

    def execute_write(self, node_id: int, new_stars: int) -> bool:
        self.graph.query(
            "MATCH (d:Developer {node_id: $id}) SET d.stars = $stars",
            {"id": node_id, "stars": new_stars},
        )
        return True

    def get_footprint(self) -> Dict[str, Any]:
        return {
            "deployment":       "Self-hosted Docker (falkordb/falkordb:latest)",
            "vCPU":             "0.5 vCPU (capped via docker deploy limits)",
            "RAM_allocated_MB": 512,
            "storage":          "In-memory GraphBLAS sparse matrices over Redis engine",
            "region":           "Localhost (Docker bridged network)",
            "memory_usage":     "Observable via Redis INFO memory",
            "stored_data_size": "Observable via Redis INFO memory",
            "note":             "Runs in local Docker container with explicit 0.5 vCPU and 512MB RAM resource caps for strict parity.",
        }
