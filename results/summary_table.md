## 📊 Benchmark Results Matrix

### 1. Data Ingestion Performance

| Platform      |   Nodes Loaded |   Edges Loaded | Total Wall-Clock Time   |   Nodes/sec |   Rels/sec |
|---------------|----------------|----------------|-------------------------|-------------|------------|
| CognoDB Cloud |         37,700 |        100,000 | 54.38s                  |       693.3 |     1839   |
| Neo4j         |         37,700 |        394,213 | 58.74s                  |       641.8 |     6711.1 |
| Memgraph      |         37,700 |        394,213 | 14.62s                  |      2578.7 |    26964   |
| FalkorDB      |         37,700 |        394,213 | 19.35s                  |      1948.3 |    20372.8 |
| Kùzu          |         37,700 |        394,213 | 0.47s                   |     80896.8 |   845904   |

### 2. Traversal Latency (p50 / p95 in ms)

| Platform      | 1-Hop (p50/p95 ms)   | 2-Hop (p50/p95 ms)   | 3-Hop (p50/p95 ms)   |
|---------------|----------------------|----------------------|----------------------|
| CognoDB Cloud | 256.93 / 257.53      | 256.83 / 257.84      | 257.09 / 257.64      |
| Neo4j         | 3.73 / 6.13          | 15.12 / 16.51        | 53.12 / 59.14        |
| Memgraph      | 1.27 / 1.54          | 3.55 / 4.21          | 13.27 / 18.23        |
| FalkorDB      | 1.81 / 2.46          | 6.97 / 8.01          | 26.33 / 29.81        |
| Kùzu          | 0.00 / 0.00          | 0.02 / 0.02          | 0.10 / 0.14          |

### 3. Lookups & Aggregations (p50 / p95 in ms)

| Platform      | Point Lookup (p50/p95 ms)   | Indexed Filter Lookup (p50/p95 ms)   | Group-by Aggregation (p50/p95 ms)   |
|---------------|-----------------------------|--------------------------------------|-------------------------------------|
| CognoDB Cloud | 256.35 / 256.40             | 607.61 / 616.60                      | 1170.87 / 1198.82                   |
| Neo4j         | 4.23 / 4.43                 | 8.17 / 11.51                         | 14.45 / 18.13                       |
| Memgraph      | 1.38 / 1.67                 | 4.06 / 4.91                          | 4.55 / 6.18                         |
| FalkorDB      | 1.34 / 2.00                 | 5.60 / 7.78                          | 6.62 / 8.51                         |
| Kùzu          | 0.00 / 0.00                 | 0.39 / 1.34                          | 3.62 / 5.62                         |

### 4. Mixed Concurrency Throughput (80% Read / 20% Write)

| Platform      | 1 Client Throughput          | 10 Clients Throughput   | 40 Clients Throughput   |
|---------------|------------------------------|-------------------------|-------------------------|
| CognoDB Cloud | 3.6 QPS (p95: 329.6ms)       | 0.0 QPS (p95: 0.0ms)    | 0.0 QPS (p95: 0.0ms)    |
| Neo4j         | 182.8 QPS (p95: 7.9ms)       | 0.0 QPS (p95: 0.0ms)    | 0.0 QPS (p95: 0.0ms)    |
| Memgraph      | 592.4 QPS (p95: 2.3ms)       | 0.0 QPS (p95: 0.0ms)    | 0.0 QPS (p95: 0.0ms)    |
| FalkorDB      | 522.8 QPS (p95: 2.6ms)       | 0.0 QPS (p95: 0.0ms)    | 0.0 QPS (p95: 0.0ms)    |
| Kùzu          | 3,114,158.8 QPS (p95: 0.0ms) | 0.0 QPS (p95: 0.0ms)    | 0.0 QPS (p95: 0.0ms)    |

### 5. Hardware Specs & Resource Footprint Parity

| Platform      | vCPU Allocation       | RAM Allocation       | Memory Behavior                           | Storage Representation               |
|---------------|-----------------------|----------------------|-------------------------------------------|--------------------------------------|
| CognoDB Cloud | 0.5 (burstable)       | 256 MB               | Cloud Managed                             | Observable in CognoDB Cloud Console  |
| Neo4j         | 0.5 (capped)          | 512 MB               | JVM Heap capped at 384m                   | Observable via sysinfo               |
| Memgraph      | 0.5 (capped)          | 256 MB               | Observable via Memgraph SHOW STORAGE INFO | In-memory representation             |
| FalkorDB      | 0.5 (capped)          | 256 MB               | Observable via Redis INFO memory          | Sparse CSR/CSC Matrix representation |
| Kùzu          | 0.5 (1 worker thread) | 256 MB (Buffer Pool) | Bounded by 256 MB buffer pool limit       | Vectorized CSR files                 |

