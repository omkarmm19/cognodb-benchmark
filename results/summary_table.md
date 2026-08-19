## 📊 Benchmark Results

> **Run config:** 100 measured iterations, 20 warmup | Dataset: 37,700 nodes, 394,213 edges | Seed: 42 | Generated: 2026-08-19T08:11:00.789645+00:00

### ⚠️ Platforms Not Benchmarked

| Platform   | Reason                                          |
|------------|-------------------------------------------------|
| Memgraph   | Connection failed or credentials not configured |
| FalkorDB   | Connection failed or credentials not configured |
| Kùzu       | Connection failed or credentials not configured |

### 1. Data Ingestion Performance

| Platform      |   Nodes Loaded |   Edges Loaded | Wall-Clock Time   |   Nodes/sec |   Rels/sec |
|---------------|----------------|----------------|-------------------|-------------|------------|
| CognoDB Cloud |         37,700 |        394,213 | 101.2s            |         373 |      3,897 |
| Neo4j         |         37,700 |        394,213 | 94.4s             |         400 |      4,178 |

### 2. Traversal Latency (p50 / p95 ms — lower is better)

| Platform      | 1-Hop p50/p95   | 2-Hop p50/p95   | 3-Hop p50/p95   |
|---------------|-----------------|-----------------|-----------------|
| CognoDB Cloud | 270.4 / 428.2   | 273.2 / 423.3   | 301.5 / 608.4   |
| Neo4j         | 77.4 / 219.0    | 77.5 / 85.9     | 78.1 / 148.7    |

### 3. Lookups & Aggregations (p50 / p95 ms — lower is better)

| Platform      | Point Lookup   | Indexed Filter   | Group-by Aggregation   |
|---------------|----------------|------------------|------------------------|
| CognoDB Cloud | 269.3 / 372.5  | 511.6 / 773.1    | 2445.9 / 2811.7        |
| Neo4j         | 77.6 / 216.7   | 100.7 / 374.4    | 160.5 / 291.7          |

### 4. Mixed Concurrency Throughput (80% Read / 20% Write)

| Platform      | 1 Client          | 10 Clients         | 40 Clients          |
|---------------|-------------------|--------------------|---------------------|
| CognoDB Cloud | 1 QPS  p95=1333ms | 10 QPS  p95=3654ms | 65 QPS  p95=1078ms  |
| Neo4j         | 7 QPS  p95=171ms  | 30 QPS  p95=735ms  | 127 QPS  p95=1027ms |

### 5. Resource Footprint

| Platform      | Deployment                                 | RAM (MB)                                                             | Memory Usage                            |
|---------------|--------------------------------------------|----------------------------------------------------------------------|-----------------------------------------|
| CognoDB Cloud | Managed Cloud — CognoDB Cloud c0 free tier | 512                                                                  | Not directly observable (managed cloud) |
| Neo4j         | Cloud — Neo4j AuraDB Free tier             | Not observable (managed cloud; free tier ~ 1 GB heap stated in docs) | Not observable                          |

