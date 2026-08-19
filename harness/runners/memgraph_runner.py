"""
Memgraph Benchmark Runner
--------------------------
Connects to Memgraph via Bolt protocol (uses the neo4j Python driver,
which is compatible with Memgraph's OpenCypher Bolt interface).

Supported targets:
  - Memgraph Cloud free tier (bolt+s://...)
  - Local Memgraph via Docker (bolt://localhost:7688)

If Memgraph is not reachable this runner returns connected=False and
the orchestrator records it as "unavailable". No simulated results.

Docs:  https://memgraph.com/docs
Docker image: memgraph/memgraph-platform
"""

import os
import csv
import time
from typing import Dict, Any, List, Optional

from neo4j import GraphDatabase
from harness.base import BaseGraphRunner


class MemgraphRunner(BaseGraphRunner):
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("Memgraph", config or {})
        self.uri = self.config.get("MEMGRAPH_URI") or os.getenv("MEMGRAPH_URI", "")
        self.user = self.config.get("MEMGRAPH_USER") or os.getenv("MEMGRAPH_USER", "")
        self.password = self.config.get("MEMGRAPH_PASSWORD") or os.getenv("MEMGRAPH_PASSWORD", "")
        self.driver = None

    def connect(self) -> bool:
        if not self.uri:
            print(f"[{self.name}] MEMGRAPH_URI not set in .env — skipping.")
            return False
        try:
            print(f"[{self.name}] Connecting to {self.uri}...")
            auth = (self.user, self.password) if self.user else None
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=auth,
                max_connection_pool_size=50,
            )
            self.driver.verify_connectivity()
            self.connected = True
            print(f"[{self.name}] Connected successfully.")
            return True
        except Exception as e:
            print(f"[{self.name}] Connection failed: {e}")
            self.connected = False
            return False

    def close(self):
        if self.driver:
            self.driver.close()
        self.connected = False

    def clear_database(self) -> bool:
        if not self.driver:
            return False
        try:
            with self.driver.session() as s:
                s.run("MATCH (n) DETACH DELETE n")
            print(f"[{self.name}] Database cleared.")
            return True
        except Exception as e:
            print(f"[{self.name}] Warning clearing db: {e}")
            return False

    def create_indices(self) -> bool:
        if not self.driver:
            return False
        try:
            with self.driver.session() as s:
                # Memgraph uses different index syntax
                s.run("CREATE INDEX ON :Developer(node_id)")
                s.run("CREATE INDEX ON :Developer(stars)")
            print(f"[{self.name}] Indices created: :Developer(node_id), :Developer(stars).")
            return True
        except Exception as e:
            print(f"[{self.name}] Index creation warning: {e}")
            return False

    def load_dataset(
        self, nodes_csv: str, edges_csv: str, batch_size: int = 1000
    ) -> Dict[str, Any]:
        t_start = time.perf_counter()
        total_nodes = 0
        total_edges = 0

        # Nodes
        print(f"[{self.name}] Ingesting nodes...")
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

        # Edges
        print(f"[{self.name}] Ingesting relationships...")
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

        t_total = time.perf_counter() - t_start
        return {
            "platform":          self.name,
            "total_nodes":       total_nodes,
            "total_edges":       total_edges,
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
        with self.driver.session() as s:
            s.run(query, batch=batch)

    def _insert_edges(self, batch: List[Dict[str, Any]]) -> None:
        query = """
        UNWIND $batch AS row
        MATCH (a:Developer {node_id: row.source_id})
        MATCH (b:Developer {node_id: row.target_id})
        CREATE (a)-[:FOLLOWS {weight: row.weight}]->(b)
        """
        with self.driver.session() as s:
            s.run(query, batch=batch)

    def point_lookup(self, node_id: int) -> Optional[Any]:
        query = (
            "MATCH (d:Developer {node_id: $id}) "
            "RETURN d.name AS name, d.stars AS stars, d.language AS lang LIMIT 1"
        )
        with self.driver.session() as s:
            return s.run(query, id=node_id).single()

    def indexed_lookup(self, min_stars: int) -> List[Any]:
        query = (
            "MATCH (d:Developer) WHERE d.stars >= $stars "
            "RETURN d.node_id AS id, d.stars AS stars LIMIT 50"
        )
        with self.driver.session() as s:
            return list(s.run(query, stars=min_stars))

    def traversal_1_hop(self, node_id: int) -> int:
        query = (
            "MATCH (d:Developer {node_id: $id})-[:FOLLOWS]->(n) "
            "RETURN count(n) AS cnt"
        )
        with self.driver.session() as s:
            res = s.run(query, id=node_id).single()
            return res["cnt"] if res else 0

    def traversal_2_hop(self, node_id: int) -> int:
        query = (
            "MATCH (d:Developer {node_id: $id})-[:FOLLOWS*2]->(n) "
            "RETURN count(DISTINCT n) AS cnt"
        )
        with self.driver.session() as s:
            res = s.run(query, id=node_id).single()
            return res["cnt"] if res else 0

    def traversal_3_hop(self, node_id: int) -> int:
        query = (
            "MATCH (d:Developer {node_id: $id})-[:FOLLOWS*3]->(n) "
            "RETURN count(DISTINCT n) AS cnt"
        )
        with self.driver.session() as s:
            res = s.run(query, id=node_id).single()
            return res["cnt"] if res else 0

    def aggregation_degree(self) -> List[Any]:
        query = """
        MATCH (d:Developer)-[r:FOLLOWS]->()
        RETURN d.language AS lang, count(r) AS rels, avg(d.stars) AS avg_stars
        ORDER BY rels DESC
        LIMIT 10
        """
        with self.driver.session() as s:
            return list(s.run(query))

    def execute_write(self, node_id: int, new_stars: int) -> bool:
        query = "MATCH (d:Developer {node_id: $id}) SET d.stars = $stars"
        with self.driver.session() as s:
            s.run(query, id=node_id, stars=new_stars)
            return True

    def get_footprint(self) -> Dict[str, Any]:
        return {
            "deployment":       "Cloud — Memgraph Cloud free tier (or local Docker)",
            "vCPU":             "Shared (free tier; exact allocation not published)",
            "RAM_allocated_MB": "Not observable (managed cloud; free tier 256 MB per docs)",
            "storage":          "In-memory (persistence optional)",
            "region":           "Configure to match CognoDB region for fairness",
            "memory_usage":     "Not directly observable (managed cloud)",
            "stored_data_size": "Observable via SHOW STORAGE INFO",
        }
