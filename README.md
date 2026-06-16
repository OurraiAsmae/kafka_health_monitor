# Kafka Health Monitor (KHM)

> **From passive monitoring to active operational intelligence.**

A lightweight, open-source Python tool that transforms Apache Kafka consumer group monitoring into proactive operational intelligence — combining a terminal CLI, a FastAPI web dashboard, predictive lag forecasting, a recommendation engine, and a full audit trail in a single Docker Compose deployment.

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-28%20passing-brightgreen)](tests/)

---

## The Problem

In every Kafka deployment, silent failures happen. A consumer group starts falling behind. Messages pile up. No warning fires because monitoring was never configured. By the time the problem is detected, the lag involves millions of messages.

**Existing tools don't go far enough:**
- Enterprise solutions (Confluent Control Center, Datadog) → expensive, require dedicated infrastructure
- Java-based tools (Kafdrop, kafka-ui) → JVM overhead, opaque to Python teams
- Burrow (LinkedIn) → no dashboard, no history, no recommendations
- Python scripts → no persistence, no alerting, no forecasting

**KHM fills the gap** — lightweight enough for a laptop, complete enough for production.

---

## Key Features

| Feature | CLI | Web |
|---|:---:|:---:|
| Real-time lag monitoring | ✅ | ✅ |
| OK / WARNING / CRITICAL alerts | ✅ | ✅ |
| Consumer Group State (STABLE/EMPTY/DEAD/REBALANCING) | ✅ | ✅ |
| Multi-cluster support with filtering | ✅ | ✅ |
| SQLite lag history | ✅ | ✅ |
| Predictive Lag Forecasting (linear regression + R²) | — | ✅ |
| Interactive forecast chart | — | ✅ |
| Global Health Score (A–E grade) | — | ✅ |
| Intelligent Recommendation Engine | ✅ | ✅ |
| System Audit Trail (CSV/JSON export) | — | ✅ |
| Statistics page (top topics, 24h timeline) | — | ✅ |
| Configuration page (live threshold updates) | — | ✅ |
| Prometheus `/metrics` export | — | ✅ |
| Dark / Light mode | — | ✅ |

---

## Quick Start

### One command — full environment

```bash
git clone https://github.com/OurraiAsmae/kafka_health_monitor.git
cd kafka_health_monitor
docker-compose up -d
```

Open **http://localhost:8080** — dashboard ready in ~30 seconds.

This starts everything: Kafka, Zookeeper, a demo producer, a slow consumer (lag accumulates), a fast consumer (keeps up), and the KHM dashboard.

### Local development (Kafka already running)

```bash
pip install -r requirements.txt
python main.py --mode web          # Web dashboard → http://localhost:8080
python main.py --mode cli status   # CLI snapshot
```

---

## CLI Commands

```bash
# Instant snapshot of all consumer groups
python main.py --mode cli status

# Filter by cluster
python main.py --mode cli status --cluster production

# Live auto-refresh every 5 seconds
python main.py --mode cli watch
python main.py --mode cli watch --cluster dev --interval 10

# Historical lag from SQLite
python main.py --mode cli history \
  --cluster production \
  --group slow-consumer-group \
  --topic orders \
  --hours 2
```

---

## Web Dashboard Pages

| URL | Description |
|---|---|
| `/` | Main dashboard — lag table, Health Score, forecasting |
| `/stats` | Global statistics — top topics, 24h timeline |
| `/config` | Live configuration — modify thresholds instantly |
| `/audit` | Audit trail — event timeline with CSV/JSON export |

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/status` | Current lag for all groups (JSON) |
| `GET /api/history?cluster=&group=&topic=&hours=` | Lag history (JSON) |
| `GET /api/forecast` | Predictive forecasting (JSON) |
| `GET /api/health-score` | Health Score 0–100 (JSON) |
| `GET /api/stats` | Aggregated statistics (JSON) |
| `GET /api/config` | Current configuration (JSON) |
| `POST /api/config` | Update configuration (JSON) |
| `GET /metrics` | Prometheus text format |

---

## How Lag is Calculated

```
lag(g, t, p) = LogEndOffset(t, p) − CommittedOffset(g, t, p)
```

- **LogEndOffset** — high watermark of the partition (last message produced)
- **CommittedOffset** — last message acknowledged by consumer group `g`
- **lag** — number of messages pending processing

Total lag for a consumer group on a topic = sum of per-partition lags.

Committed offsets are read using `Consumer.committed()` with the actual `group_id`, ensuring accuracy against the live Kafka state.

---

## Predictive Lag Forecasting

KHM applies ordinary least-squares linear regression to the last hour of SQLite measurements:

```
lag(t) = slope × t + intercept
```

| Output | Description |
|---|---|
| `trend` | INCREASING / DECREASING / STABLE |
| `slope_per_min` | Lag growth rate (messages/minute) |
| `r_squared` | Confidence: HIGH (≥0.85) / MEDIUM (≥0.5) / LOW |
| `eta_warning_min` | Minutes until WARNING threshold |
| `eta_critical_min` | Minutes until CRITICAL threshold |
| `predicted_lag_5min` | Predicted lag in 5 minutes |
| `predicted_lag_15min` | Predicted lag in 15 minutes |

The dashboard renders observed lag (solid blue) and regression projection (dashed orange) with WARNING and CRITICAL threshold lines.

---

## Health Score (A–E)

```
score = 100 − P_critical − P_warning − P_state

P_critical = (n_critical / n_total) × 60
P_warning  = (n_warning  / n_total) × 25
P_state    = (n_empty_or_dead / n_total) × 15
```

| Score | Grade | Meaning |
|---|---|---|
| 80–100 | **A** | All groups healthy and active |
| 60–79 | **B** | Minor issues, stable overall |
| 40–59 | **C** | Moderate lag or empty groups |
| 20–39 | **D** | Significant issues requiring attention |
| 0–19 | **E** | Systemic failure |

---

## Intelligent Recommendation Engine

KHM goes beyond displaying metrics — it tells you **what to do**.

```
[HIGH]   Scale consumer group: slow-consumer-group
         Forecast breach: CRITICAL in ~27min (R²=0.94)
         Action: Increase instances (current: 1, partitions: 3)

[MEDIUM] Topology warning: topic 'orders'
         Lag rate exceeds per-partition processing capacity
         Action: Review partition count for sustained workloads

[HIGH]   Stranded messages: batch-consumer-group / invoices
         4,200 messages pending. Group state: EMPTY
         Action: Restart consumer. Messages will NOT self-resolve.
```

---

## System Audit Trail

Every system event is logged with full metadata:

- **Configuration changes** — parameter, old value, new value, timestamp, source
- **Alert transitions** — OK → WARNING → CRITICAL with lag value at transition
- **System events** — service starts, cleanup operations, errors

Exportable in **CSV** and **JSON** from the `/audit` page.

---

## Prometheus Integration

```
# TYPE kafka_consumer_lag gauge
kafka_consumer_lag{cluster="production",group="slow-consumer-group",topic="orders"} 2700
```

Add to your Prometheus config:

```yaml
scrape_configs:
  - job_name: 'kafka-health-monitor'
    static_configs:
      - targets: ['localhost:8080']
```

---

## Configuration

```yaml
clusters:
  - name: "dev"
    bootstrap_servers: "localhost:9092"
  - name: "production"
    bootstrap_servers: "prod.host:9092"

alerts:
  warning_threshold:  1000
  critical_threshold: 10000

monitor:
  refresh_interval: 5
  history_retention_days: 7
```

---

## Project Structure

```
kafka-health-monitor/
├── core/
│   ├── kafka_client.py      # Kafka connection, offset reading, group states
│   ├── lag_calculator.py    # Lag formula, alert classification, multi-cluster
│   ├── forecasting.py       # Linear regression predictions (numpy)
│   ├── health_score.py      # Health Score 0-100, per-cluster grades
│   ├── recommender.py       # Intelligent recommendation engine
│   ├── audit.py             # System audit trail, CSV/JSON export
│   ├── stats.py             # Global statistics aggregation
│   ├── db.py                # SQLite persistence
│   └── config_loader.py     # config.yml loading with safe defaults
├── interfaces/
│   ├── cli.py               # Terminal UI (Rich + Click)
│   └── web.py               # FastAPI + Uvicorn + background collector
├── static/css/ + js/
├── templates/
│   ├── dashboard.html
│   ├── stats.html
│   ├── config.html
│   └── audit.html
├── tests/                   # 28+ unit tests
├── demo_producer.py
├── demo_consumer_slow.py
├── demo_consumer_normal.py
├── main.py
├── config.yml
├── Dockerfile
└── docker-compose.yml
```

---

## Running Tests

```bash
pip install pytest pytest-cov
pytest -v
pytest --cov=core --cov-report=term-missing
```

---

## Comparison with Existing Tools

| Feature | KHM 2.0 | Kafdrop | Burrow | kafka-ui | Scripts |
|---|:---:|:---:|:---:|:---:|:---:|
| Language | Python | Java | Go | Java | Various |
| CLI interface | ✅ | — | — | — | Partial |
| Web dashboard | ✅ | ✅ | — | ✅ | — |
| Lag history | ✅ | — | — | — | — |
| Predictive forecasting | ✅ | — | — | — | — |
| Health Score | ✅ | — | — | — | — |
| Recommendation engine | ✅ | — | — | — | — |
| Audit trail | ✅ | — | — | — | — |
| CSV/JSON export | ✅ | — | — | Partial | — |
| Prometheus export | ✅ | — | ✅ | ✅ | — |
| Multi-cluster | ✅ | Partial | — | ✅ | — |
| Docker one-command | ✅ | Medium | Hard | Medium | N/A |

---

## Academic Publication

This tool is the subject of a research article submitted to **SoftwareX (Elsevier)**:

> *Kafka Health Monitor: A Lightweight, Dual-Interface Tool for Real-Time Monitoring, Predictive Forecasting, and Operational Intelligence of Apache Kafka Consumer Groups*
>
> National School of Applied Sciences, Chouaib Doukkali University, El Jadida, Morocco

---

## License

MIT License — free to use, modify, and distribute.

---


## Authors

- **Asmae Ourrai** — [GitHub](https://github.com/OurraiAsmae)
- **Safae El Ouajidi** — [GitHub](https://github.com/elouajidisafae)
- **Marwa M'haya**

### Supervisor

- **Mohamed Hanine** — TRI

*National School of Applied Sciences — Chouaib Doukkali University, El Jadida, Morocco*
