## 📊 Benchmark Results

> **Run config:** 100 measured iterations, 20 warmup | Dataset: 37,700 nodes, 394,213 edges | Seed: 42 | Generated: 2026-08-19T11:32:36.852310+00:00

### 1. Data Ingestion Performance

| Platform      |   Nodes Loaded |   Edges Loaded | Wall-Clock Time   |   Nodes/sec |   Rels/sec |
|---------------|----------------|----------------|-------------------|-------------|------------|
| CognoDB Cloud |         37,700 |        394,213 | 428.9s            |          88 |        919 |
| Neo4j         |         37,700 |        394,213 | 100.9s            |         374 |      3,908 |
| Memgraph      |         37,700 |        394,213 | 5.1s              |       7,405 |     77,429 |
| FalkorDB      |         37,700 |        394,213 | 14.4s             |       2,614 |     27,336 |
| Kùzu          |         37,700 |        394,213 | 0.3s              |     122,922 |  1,285,346 |

### 2. Traversal Latency (p50 / p95 ms — lower is better)

| Platform      | 1-Hop p50/p95   | 2-Hop p50/p95   | 3-Hop p50/p95   |
|---------------|-----------------|-----------------|-----------------|
| CognoDB Cloud | 247.0 / 302.7   | 263.6 / 398.1   | 289.6 / 611.1   |
| Neo4j         | 99.1 / 125.0    | 77.7 / 162.5    | 76.8 / 80.7     |
| Memgraph      | 0.5 / 2.8       | 0.4 / 0.5       | 0.5 / 0.7       |
| FalkorDB      | 0.3 / 0.4       | 0.3 / 0.4       | 0.5 / 0.6       |
| Kùzu          | 0.2 / 0.2       | 0.4 / 0.4       | 0.7 / 1.3       |

### 3. Lookups & Aggregations (p50 / p95 ms — lower is better)

| Platform      | Point Lookup   | Indexed Filter   | Group-by Aggregation   |
|---------------|----------------|------------------|------------------------|
| CognoDB Cloud | 240.1 / 300.2  | 485.4 / 603.8    | 4957.6 / 6323.6        |
| Neo4j         | 76.0 / 83.6    | 78.3 / 97.7      | 160.9 / 441.0          |
| Memgraph      | 0.3 / 0.4      | 0.7 / 0.9        | 175.7 / 193.9          |
| FalkorDB      | 0.3 / 0.3      | 0.4 / 0.5        | 206.7 / 281.8          |
| Kùzu          | 0.1 / 0.1      | 0.2 / 0.6        | 5.8 / 5.9              |

### 4. Mixed Concurrency Throughput (80% Read / 20% Write)

| Platform      | 1 Client           | 10 Clients          | 40 Clients          |
|---------------|--------------------|---------------------|---------------------|
| CognoDB Cloud | 0 QPS  p95=7107ms  | 6 QPS  p95=3581ms   | 14 QPS  p95=5492ms  |
| Neo4j         | 7 QPS  p95=161ms   | 48 QPS  p95=542ms   | 146 QPS  p95=521ms  |
| Memgraph      | 1,012 QPS  p95=1ms | 1,428 QPS  p95=56ms | 1,603 QPS  p95=69ms |
| FalkorDB      | 2,283 QPS  p95=1ms | 4,732 QPS  p95=2ms  | 4,530 QPS  p95=51ms |
| Kùzu          | 905 QPS  p95=4ms   | 868 QPS  p95=23ms   | 828 QPS  p95=80ms   |

### 5. Resource Footprint

| Platform      | Deployment                                     | RAM (MB)                                                             | Memory Usage                            |
|---------------|------------------------------------------------|----------------------------------------------------------------------|-----------------------------------------|
| CognoDB Cloud | Managed Cloud — CognoDB Cloud c0 free tier     | 512                                                                  | Not directly observable (managed cloud) |
| Neo4j         | Cloud — Neo4j AuraDB Free tier                 | Not observable (managed cloud; free tier ~ 1 GB heap stated in docs) | Not observable                          |
| Memgraph      | Self-hosted Docker (memgraph/memgraph:latest)  | 512                                                                  | Observable via SHOW STORAGE INFO        |
| FalkorDB      | Self-hosted Docker (falkordb/falkordb:latest)  | 512                                                                  | Observable via Redis INFO memory        |
| Kùzu          | Embedded In-Process (Vectorized Columnar OLAP) | 512                                                                  | Bounded by 512 MB buffer pool           |

