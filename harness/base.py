"""
Base Abstract Class for Graph Database Benchmark Runners
--------------------------------------------------------
Provides uniform interfaces for connecting, indexing, ingesting data,
executing Cypher queries, aggregations, and profiling footprint.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import time

class BaseGraphRunner(ABC):
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.connected = False

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the graph database."""
        pass

    @abstractmethod
    def close(self):
        """Cleanly close connection/pool."""
        pass

    @abstractmethod
    def clear_database(self) -> bool:
        """Wipe existing graph nodes and relationships."""
        pass

    @abstractmethod
    def create_indices(self) -> bool:
        """Create indices on Developer(node_id) and Developer(stars)."""
        pass

    @abstractmethod
    def load_dataset(self, nodes_csv: str, edges_csv: str, batch_size: int = 1000) -> Dict[str, Any]:
        """Ingest nodes and edges in batches, returning wall-clock time and rates."""
        pass

    @abstractmethod
    def point_lookup(self, node_id: int) -> Any:
        """Fetch a single node by its primary ID: MATCH (d:Developer {node_id: $id}) RETURN d."""
        pass

    @abstractmethod
    def indexed_lookup(self, min_stars: int) -> List[Any]:
        """Filter nodes using indexed property: MATCH (d:Developer) WHERE d.stars >= $stars RETURN d LIMIT 50."""
        pass

    @abstractmethod
    def traversal_1_hop(self, node_id: int) -> int:
        """1-hop neighbors: MATCH (d:Developer {node_id: $id})-[:FOLLOWS]->(n) RETURN count(n)."""
        pass

    @abstractmethod
    def traversal_2_hop(self, node_id: int) -> int:
        """2-hop neighbors: MATCH (d:Developer {node_id: $id})-[:FOLLOWS*2]->(n) RETURN count(DISTINCT n)."""
        pass

    @abstractmethod
    def traversal_3_hop(self, node_id: int) -> int:
        """3-hop neighbors: MATCH (d:Developer {node_id: $id})-[:FOLLOWS*3]->(n) RETURN count(DISTINCT n)."""
        pass

    @abstractmethod
    def aggregation_degree(self) -> List[Any]:
        """Group-by style aggregation: MATCH (d:Developer)-[r:FOLLOWS]->() RETURN d.language, count(r) AS rels, avg(d.stars) ORDER BY rels DESC LIMIT 10."""
        pass

    @abstractmethod
    def execute_write(self, node_id: int, new_stars: int) -> bool:
        """Point write update: MATCH (d:Developer {node_id: $id}) SET d.stars = $stars."""
        pass

    @abstractmethod
    def get_footprint(self) -> Dict[str, Any]:
        """Return memory and disk usage metrics if observable."""
        pass
