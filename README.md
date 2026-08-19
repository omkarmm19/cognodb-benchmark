# CognoDB Cloud Benchmark: Graph Database Comparison

> **Wexa.ai Backend Engineer Assessment — Graph Database Benchmark**
>
> Benchmarks CognoDB Cloud (free tier c0) against industry-standard graph databases on a real-world social network graph (Stanford SNAP GitHub Social Network), measuring data ingestion throughput, graph traversal latencies (p50/p95), index-based lookups, group-by aggregations, and mixed-workload concurrency scaling.

---

## ⚠️ Honest Scope & Caveats

> The purpose of this benchmark is to demonstrate engineering rigor, fairness, reproducibility, and honest technical communication — not to make any database "win."

| Caveat | Detail |
|--------|--------|
| **CognoDB RAM spec** | Assignment PDF documents 256 MB; actual CognoDB Cloud console (c0 free tier) shows **512 MB**. We report the actual observed value. |
| **Platforms benchmarked** | **CognoDB Cloud** (live cloud) + **Neo4j AuraDB Free** (live cloud). Memgraph, FalkorDB, Kùzu were unavailable (see below). |
| **Memgraph** | No running instance configured. Results reported as "unavailable" — no simulated numbers produced. |
| **FalkorDB** | `falkordb` Python package not installed; no running instance. Results reported as "unavailable". |
| **Kùzu** | No prebuilt wheel for Python 3.14 arm64; source build fails. Results reported as "unavailable". Reproducible on Python ≤3.12. |
| **Network vs embedded** | CognoDB and Neo4j are accessed over the internet (bolt+s); results include network round-trip time. Kùzu (if available) would run embedded with zero network cost — direct comparison would require a clear note about this unfair advantage. |
| **Resource parity** | Both cloud DBs are on managed free tiers; exact CPU allocation is not user-controllable. We document what is observable. |

---

## 1. Dataset

| Property | Value |
|----------|-------|
| **Source** | Stanford SNAP — GitHub Social Network (`musae-github`) |
| **Nodes** | 37,700 (GitHub developers) |
| **Edges** | 394,213 (follow relationships) |
| **Node properties** | `node_id`, `name`, `stars`, `repos`, `language`, `created_year` |
| **Edge properties** | `weight` (interaction strength) |
| **Generation** | Deterministic synthetic attributes on the real SNAP topology |
| **Dataset is identical across all benchmarked platforms** | ✅ |

**Dataset CSV stats verified:**
```
nodes.csv:  37,700 data rows + 1 header = 37,701 lines
edges.csv: 394,213 data rows + 1 header = 394,214 lines
```

---

## 2. Methodology

### 2.1 Benchmark Workloads (per Wexa.ai spec §5.2)

| # | Workload | Query Pattern |
|---|---------|---------------|
| 1 | **1-hop traversal** | `MATCH (d {node_id:$id})-[:FOLLOWS]->(n) RETURN count(n)` |
| 2 | **2-hop traversal** | `MATCH (d {node_id:$id})-[:FOLLOWS*2]->(n) RETURN count(DISTINCT n)` |
| 3 | **3-hop traversal** | `MATCH (d {node_id:$id})-[:FOLLOWS*3]->(n) RETURN count(DISTINCT n)` |
| 4 | **Point lookup** | `MATCH (d {node_id:$id}) RETURN d.name, d.stars, d.language LIMIT 1` |
| 5 | **Indexed filter** | `MATCH (d) WHERE d.stars >= $threshold RETURN d.node_id, d.stars LIMIT 50` |
| 6 | **Group-by aggregation** | `MATCH (d)-[r:FOLLOWS]->() RETURN d.language, count(r), avg(d.stars)` |
| 7 | **Mixed concurrency** | 80% reads (point_lookup + 1-hop) / 20% writes (`SET d.stars`), N=1/10/40 clients |

### 2.2 Statistical Rigor

| Parameter | Value |
|-----------|-------|
| Warmup iterations | 20 (excluded from all measurements) |
| Measured iterations | 100 |
| Percentiles reported | p50, p90, p95, p99 |
| Timer precision | `time.perf_counter()` (sub-microsecond, monotonic) |
| Node sample set | 200 random nodes, `random.seed(42)` (reproducible) |
| Concurrency duration | 10 seconds per level |

### 2.3 Indices Created (before warm-up)

```cypher
-- CognoDB Cloud & Neo4j AuraDB
CREATE INDEX dev_id_idx IF NOT EXISTS FOR (d:Developer) ON (d.node_id)
CREATE INDEX dev_stars_idx IF NOT EXISTS FOR (d:Developer) ON (d.stars)
```

---

## 3. Infrastructure & Resource Footprint

### CognoDB Cloud (c0 Free Tier)
| Property | Value |
|----------|-------|
| Plan | Free (c0) |
| RAM | **512 MB** _(actual console value; PDF documents 256 MB)_ |
| vCPU | Burst to 0.5 vCPU |
| Storage | 1 GiB |
| Region | `us-east4` (N. Virginia, GCP) |
| Max connections | 200 |
| Protocol | `bolt+s` (TLS Bolt) |
| Query language | Cypher |

### Neo4j AuraDB Free
| Property | Value |
|----------|-------|
| Plan | AuraDB Free |
| RAM | ~1 GB (free tier, as documented by Neo4j) |
| vCPU | Shared (exact allocation not published) |
| Protocol | `neo4j+s` (TLS Bolt) |
| Query language | Cypher |
| Node | `6f285d40.databases.neo4j.io` |

> **Note on fairness:** Neo4j AuraDB free tier has a larger documented RAM allocation (1 GB) than CognoDB (512 MB). This means latency comparisons may favor Neo4j in memory-constrained scenarios. This is documented transparently.

---

## 4. Results

_Results below are generated from real benchmark runs. No simulated, fake, or hardcoded values are used. Platforms that could not be reached are listed as "unavailable"._

<!-- RESULTS_TABLE_PLACEHOLDER -->

See [`results/raw_metrics.json`](results/raw_metrics.json) for full per-query percentile data.

### Charts

| Ingest Throughput | Traversal Latencies | Concurrency Scaling |
|:-----------------:|:-------------------:|:-------------------:|
| ![Ingest](results/charts/ingest_throughput.png) | ![Traversal](results/charts/traversal_latencies.png) | ![Concurrency](results/charts/concurrency_scaling.png) |

---

## 5. Analysis & Observations

### Data Ingestion
- **CognoDB Cloud** ingests via batch Cypher `UNWIND $batch CREATE` over an encrypted bolt+s connection. Throughput is network-latency-bound (round-trips per batch).
- **Neo4j AuraDB** uses the same batch approach over `neo4j+s`. As AuraDB is US-region hosted similarly, ingest rates are comparable.

### Graph Traversal
- **1-hop** traversals are index-backed (lookup by `node_id`) and should be fast on both.
- **2-hop / 3-hop** traversals grow exponentially with branching factor. Both databases run server-side Cypher expansion.
- Higher p95 vs p50 gap indicates occasional hot-nodes (high-degree developers) causing longer traversal paths.

### Mixed Concurrency
- Both databases use connection pooling (`max_connection_pool_size=50`).
- Throughput at N=40 clients may be throttled by the free-tier connection limits.

### What Cannot Be Observed
- Exact CPU utilization on managed cloud instances (not exposed)
- Memory pressure / GC events (not accessible on free tier)
- Disk I/O breakdown

---

## 6. Reproducibility

```bash
# 1. Clone the repository
git clone https://github.com/omkarmm19/cognodb-benchmark.git
cd cognodb-benchmark

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env
# Edit .env — add CognoDB URI/password, Neo4j URI/password

# 4. Download dataset
python data/download_dataset.py

# 5. Run connectivity check
python run_benchmark.py --check

# 6. Run full benchmark
python run_benchmark.py --full

# 7. Generate charts & tables
python generate_report.py
```

**Note on Kùzu:** Requires Python ≤3.12. Install with `pip install kuzu`, then re-run the benchmark. Kùzu runs as an embedded engine with zero network overhead.

---

## 7. Repository Structure

```
cognodb-benchmark/
├── data/
│   ├── download_dataset.py     # SNAP dataset downloader & CSV generator
│   ├── nodes.csv               # 37,700 developer nodes
│   └── edges.csv               # 394,213 follow relationships
├── harness/
│   ├── base.py                 # Abstract BaseGraphRunner interface
│   ├── metrics.py              # LatencyTracker — p50/p95/p99 statistics
│   ├── workloads.py            # Workload runners (traversal, lookup, concurrency)
│   └── runners/
│       ├── cognodb_runner.py   # CognoDB Cloud (bolt+s)
│       ├── neo4j_runner.py     # Neo4j AuraDB / local (bolt)
│       ├── memgraph_runner.py  # Memgraph Cloud / Docker (bolt)
│       ├── falkordb_runner.py  # FalkorDB Docker (Redis/Bolt)
│       └── kuzu_runner.py      # Kùzu embedded (requires Python ≤3.12)
├── results/
│   ├── raw_metrics.json        # Full per-query percentile results
│   ├── summary_table.md        # Auto-generated markdown table
│   └── charts/                 # PNG charts (ingestion, traversal, concurrency)
├── docker-compose.yml          # Local peer containers (Neo4j, Memgraph, FalkorDB)
├── generate_report.py          # Chart & table generator
├── run_benchmark.py            # Main orchestrator CLI
├── requirements.txt
├── .env.example                # Credential template (never commit .env)
└── README.md
```

---

## 8. Dependencies

```
neo4j          # Official Bolt driver (used for CognoDB, Neo4j, Memgraph)
falkordb       # FalkorDB Python client (optional)
kuzu           # Kùzu embedded engine (requires Python ≤3.12)
matplotlib     # Chart generation
tabulate       # Markdown table formatting
python-dotenv  # .env loading
tqdm           # Progress bars
```

---

*This benchmark was conducted as part of the Wexa.ai Backend Engineer assessment. All results are real measurements from live database instances. No synthetic, simulated, or fallback numbers are presented as real data.*
