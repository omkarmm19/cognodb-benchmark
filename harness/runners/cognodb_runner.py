"""
CognoDB Cloud Benchmark Runner
-------------------------------
Connects to CognoDB Cloud free tier (c0) using the official Neo4j Bolt Driver.

Actual instance specs (verified from CognoDB console):
  Plan:            Free (c0)
  RAM:             512 MB
  vCPU:            Burst to 0.5 vCPU
  Storage:         1 GiB
  Max connections: 200
  Region:          us-east4 (N. Virginia)

Protocol:         bolt+s (TLS encrypted Bolt)
Query Language:   Cypher (compatible with neo4j Python driver)

Note: The assignment PDF describes 256 MB RAM for the free tier, but the actual
current CognoDB console shows 512 MB. We use the observed value and note the
discrepancy in caveats.
"""

import os
import csv
import time
from typing import Dict, Any, List, Optional

from neo4j import GraphDatabase
from harness.base import BaseGraphRunner


class CognoDBRunner(BaseGraphRunner):
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("CognoDB Cloud", config or {})
        self.uri = self.config.get("COGNODB_URI") or os.getenv("COGNODB_URI", "")
        self.user = self.config.get("COGNODB_USER") or os.getenv("COGNODB_USER", "cognodb")
        self.password = self.config.get("COGNODB_PASSWORD") or os.getenv("COGNODB_PASSWORD", "")
        self.driver = None

    def connect(self) -> bool:
        if not self.uri or not self.password:
            print(f"[{self.name}] COGNODB_URI or COGNODB_PASSWORD not set in .env — skipping.")
            return False
        try:
            print(f"[{self.name}] Connecting to {self.uri} as '{self.user}'...")
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
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
            with self.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            print(f"[{self.name}] Database cleared.")
            return True
        except Exception as e:
            print(f"[{self.name}] Warning clearing db: {e}")
            return False

    def create_indices(self) -> bool:
        if not self.driver:
            return False
        try:
            with self.driver.session() as session:
                session.run(
                    "CREATE INDEX dev_id_idx IF NOT EXISTS FOR (d:Developer) ON (d.node_id)"
                )
                session.run(
                    "CREATE INDEX dev_stars_idx IF NOT EXISTS FOR (d:Developer) ON (d.stars)"
                )
            print(f"[{self.name}] Indices created: Developer(node_id), Developer(stars).")
            return True
        except Exception as e:
            print(f"[{self.name}] Index creation warning: {e}")
            return False

    def load_dataset(
        self, nodes_csv: str, edges_csv: str, batch_size: int = 2000
    ) -> Dict[str, Any]:
        """
        Loads the full dataset — identical node and edge set as every other runner.
        No edge limit is applied; all 394,213 relationships are ingested.
        """
        t_start = time.perf_counter()
        total_nodes = 0
        total_edges = 0

        # Nodes
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
                    self._insert_nodes_batch(batch)
                    total_nodes += len(batch)
                    print(f"[{self.name}]   nodes: {total_nodes:,}", end="\r")
                    batch = []
            if batch:
                self._insert_nodes_batch(batch)
                total_nodes += len(batch)
        print(f"\n[{self.name}] Nodes ingested: {total_nodes:,}")

        # Edges
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
                    self._insert_edges_batch(batch)
                    total_edges += len(batch)
                    print(f"[{self.name}]   edges: {total_edges:,}", end="\r")
                    batch = []
            if batch:
                self._insert_edges_batch(batch)
                total_edges += len(batch)
        print(f"\n[{self.name}] Edges ingested: {total_edges:,}")

        t_total = time.perf_counter() - t_start
        return {
            "platform":         self.name,
            "total_nodes":      total_nodes,
            "total_edges":      total_edges,
            "wall_clock_time_s": round(t_total, 2),
            "nodes_per_sec":    round(total_nodes / t_total, 2) if t_total > 0 else 0,
            "rels_per_sec":     round(total_edges / t_total, 2) if t_total > 0 else 0,
        }

    def _insert_nodes_batch(self, batch: List[Dict[str, Any]]) -> None:
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
        with self.driver.session() as session:
            session.run(query, batch=batch)

    def _insert_edges_batch(self, batch: List[Dict[str, Any]]) -> None:
        query = """
        UNWIND $batch AS row
        MATCH (a:Developer {node_id: row.source_id})
        MATCH (b:Developer {node_id: row.target_id})
        CREATE (a)-[:FOLLOWS {weight: row.weight}]->(b)
        """
        with self.driver.session() as session:
            session.run(query, batch=batch)

    def point_lookup(self, node_id: int) -> Optional[Any]:
        # Uses index on Developer(node_id)
        query = (
            "MATCH (d:Developer {node_id: $id}) "
            "RETURN d.name AS name, d.stars AS stars, d.language AS lang LIMIT 1"
        )
        with self.driver.session() as session:
            return session.run(query, id=node_id).single()

    def indexed_lookup(self, min_stars: int) -> List[Any]:
        # Uses index on Developer(stars)
        query = (
            "MATCH (d:Developer) WHERE d.stars >= $stars "
            "RETURN d.node_id AS id, d.stars AS stars, d.language AS lang LIMIT 50"
        )
        with self.driver.session() as session:
            return list(session.run(query, stars=min_stars))

    def traversal_1_hop(self, node_id: int) -> int:
        query = (
            "MATCH (d:Developer {node_id: $id})-[:FOLLOWS]->(n) "
            "RETURN count(n) AS cnt"
        )
        with self.driver.session() as session:
            res = session.run(query, id=node_id).single()
            return res["cnt"] if res else 0

    def traversal_2_hop(self, node_id: int) -> int:
        query = (
            "MATCH (d:Developer {node_id: $id})-[:FOLLOWS*2]->(n) "
            "RETURN count(DISTINCT n) AS cnt"
        )
        with self.driver.session() as session:
            res = session.run(query, id=node_id).single()
            return res["cnt"] if res else 0

    def traversal_3_hop(self, node_id: int) -> int:
        query = (
            "MATCH (d:Developer {node_id: $id})-[:FOLLOWS*3]->(n) "
            "RETURN count(DISTINCT n) AS cnt"
        )
        with self.driver.session() as session:
            res = session.run(query, id=node_id).single()
            return res["cnt"] if res else 0

    def aggregation_degree(self) -> List[Any]:
        query = """
        MATCH (d:Developer)-[r:FOLLOWS]->()
        RETURN d.language AS lang, count(r) AS rels, avg(d.stars) AS avg_stars
        ORDER BY rels DESC
        LIMIT 10
        """
        with self.driver.session() as session:
            return list(session.run(query))

    def execute_write(self, node_id: int, new_stars: int) -> bool:
        query = "MATCH (d:Developer {node_id: $id}) SET d.stars = $stars"
        with self.driver.session() as session:
            session.run(query, id=node_id, stars=new_stars)
            return True

    def get_footprint(self) -> Dict[str, Any]:
        return {
            "deployment":          "Managed Cloud — CognoDB Cloud c0 free tier",
            "region":              "us-east4 (N. Virginia)",
            "vCPU":                "Burst to 0.5 vCPU",
            "RAM_allocated_MB":    512,
            "storage_GiB":         1,
            "max_connections":     200,
            "memory_usage":        "Not directly observable (managed cloud)",
            "stored_data_size":    "Observable in CognoDB Cloud Console",
            "note":                (
                "Assignment PDF documents 256 MB RAM; actual CognoDB console shows 512 MB. "
                "We report the observed/actual value."
            ),
        }
