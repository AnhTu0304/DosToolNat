# dos-tool

Controlled HTTP load, resilience, and multi-stage scenario testing tool for security and performance assessment of web applications that you own or have explicit permission to test.

---

## 1. Project Overview

`dos-tool` is an independent, controlled HTTP resilience and load testing utility. It is designed to assist system architects, developers, and security professionals in assessing web service availability, performance characteristics, and stability under controlled conditions.

> [!IMPORTANT]
> **Authorized Use Only:** This tool is strictly intended for testing targets that you own or have explicit, documented authorization to test. Unauthorized denial-of-service testing against third-party systems is illegal and violates acceptable use policies.

This project is fully standalone and has no dependency on separate AI self-healing or remediation frameworks.

---

## 2. Current Scope

This repository currently implements:
* **Phase 1 — Project Foundation** (CLI, Configuration, Safety Controls, Logging, Basic HTTP Test)
* **Phase 2 — Controlled HTTP Load Engine** (Asynchronous Load Engine, Concurrency & Rate Limiting, Latency Percentiles)
* **Phase 3 — Scenario Engine** (Declarative Multi-Stage YAML Scenarios, Stage Orchestration, Aggregated Reporting)

### Implemented Features:
* **CLI Interface (Typer + Rich)**:
  * `dos-tool --help`
  * `dos-tool version`
  * `dos-tool config`
  * `dos-tool test` (Single HTTP connectivity probe)
  * `dos-tool load` (Asynchronous controlled load test)
  * `dos-tool scenario list` (Discover and list available YAML scenarios)
  * `dos-tool scenario show <name>` (Inspect scenario stages and duration without sending traffic)
  * `dos-tool scenario run <name>` (Execute multi-stage scenario sequentially)
* **Scenario Engine**:
  * YAML-based scenario definition in `scenarios/`.
  * Multi-stage sequential execution reusing the Phase 2 Load Engine.
  * Real-time stage progress telemetry and comprehensive stage summary table.
  * Preserves exact per-stage percentiles (P95, P99) without statistical distortion.
* **Safety Controls**:
  * Pre-execution parameter validation enforcing URL schemes, hosts, timeouts, duration, and rate limits.
  * **Total Scenario Duration Rule**: Rejects scenarios if the sum of all stage durations exceeds `max_test_duration`.
* **Logging System**: Sanitized console logging without sensitive headers, credentials, or cookies.
* **Unit Test Suite**: 78 automated unit tests using pytest and mock HTTP transports.

> [!NOTE]
> **Scope Restrictions:**
> The load engine and scenario engine are strictly **GET-only** to prevent mutating state or ecommerce data.
> No IP rotation, proxy rotation, WAF bypass, CAPTCHA bypass, distributed attacks, or stealth evasion mechanisms are implemented.

---

## 3. Installation

### Requirements
* Python 3.12+ (tested with Python 3.14)
* Virtual environment recommended

### Windows Setup (PowerShell / CMD)

```powershell
# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment
.venv\Scripts\activate

# 3. Install dependencies and package
pip install -r requirements.txt
pip install -e .
```

### Git Bash (MINGW64) Setup

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment in Git Bash
source .venv/Scripts/activate

# 3. Install dependencies and package
pip install -r requirements.txt
pip install -e .
```

### Linux / macOS Setup

```bash
# 1. Create virtual environment
python3 -m venv .venv

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install dependencies and package
pip install -r requirements.txt
pip install -e .
```

---

## 4. Usage

### 1. Show Help & Version
```bash
dos-tool --help
dos-tool version
```
*Output:*
```text
dos-tool version 0.3.0 (Phase 3 - Scenario Engine)
```

### 2. View Configuration & Safety Limits
```bash
dos-tool config
```

### 3. Basic HTTP Connectivity Test (Single Request)
```bash
dos-tool test --target http://localhost:3000
```

### 4. Controlled Single-Stage Load Test
```bash
dos-tool load --target http://localhost:3000 --rate 10 --concurrency 5 --duration 20
```

### 5. Multi-Stage Scenario Engine (Phase 3)

#### List Available Scenarios
```bash
dos-tool scenario list
```
*Output:*
```text
Available Scenarios
--------------------------------
ecommerce_product_ramp
frontend_load
```

#### Inspect Scenario Details
```bash
dos-tool scenario show ecommerce_product_ramp
```
*Output:*
```text
Scenario
--------------------------------
Name        : ecommerce_product_ramp
Description : Controlled ramp-up test for ecommerce product API
Target      : http://localhost:5000/api/products
Method      : GET

Stages:

1. Rate=2 req/s, Concurrency=1, Duration=10s
2. Rate=5 req/s, Concurrency=2, Duration=10s
3. Rate=10 req/s, Concurrency=5, Duration=10s
4. Rate=20 req/s, Concurrency=10, Duration=10s

Total Duration: 40s
```

#### Execute a Scenario
```bash
dos-tool scenario run frontend_load
```

*Example Terminal Output:*
```text
DOS TOOL - SCENARIO TEST
================================================

Scenario      : frontend_load
Description   : Controlled load test for ecommerce frontend
Target        : http://localhost:3000
Method        : GET

================================================
Stage 1/3
------------------------------------------------
Rate          : 2 req/s
Concurrency   : 1
Duration      : 10s

Total Requests: 20
Successful    : 20
Failed        : 0
P95           : 20.4 ms
P99           : 243.7 ms
Actual RPS    : 1.96

================================================
Stage 2/3
------------------------------------------------
Rate          : 5 req/s
Concurrency   : 2
Duration      : 10s

Total Requests: 50
Successful    : 50
Failed        : 0
P95           : 5.3 ms
P99           : 267.1 ms
Actual RPS    : 4.93

================================================
Stage 3/3
------------------------------------------------
Rate          : 10 req/s
Concurrency   : 5
Duration      : 10s

Total Requests: 100
Successful    : 100
Failed        : 0
P95           : 4.9 ms
P99           : 268.8 ms
Actual RPS    : 9.85

================================================
SCENARIO RESULT
================================================

Scenario          : frontend_load
Target            : http://localhost:3000
Total Duration    : 30.5 s

Total Requests    : 170
Successful        : 170
Failed            : 0
Timeouts          : 0
Connection Errors : 0

------------------------------------------------
STAGE SUMMARY
------------------------------------------------

 Stage  Rate  Concurrency  Requests  Success  Failed      P95       P99 
     1     2            1        20       20       0  20.4 ms  243.7 ms 
     2     5            2        50       50       0   5.3 ms  267.1 ms 
     3    10            5       100      100       0   4.9 ms  268.8 ms 

================================================
```

---

## 5. Scenario YAML Format

Scenarios are defined in YAML files located in `scenarios/`:

```yaml
name: ecommerce_product_ramp
description: Controlled ramp-up test for ecommerce product API
target: http://localhost:5000/api/products
method: GET

stages:
  - rate: 2
    concurrency: 1
    duration: 10

  - rate: 5
    concurrency: 2
    duration: 10

  - rate: 10
    concurrency: 5
    duration: 10

  - rate: 20
    concurrency: 10
    duration: 10
```

---

## 6. Safety Guardrails & Validation

All executions are validated prior to dispatch:
1. Target URL format & scheme (`http`/`https` with host).
2. Per-stage rate, concurrency, duration within configured maximums.
3. Cumulative scenario duration must not exceed `max_test_duration` (default: 60s).

Default limits in `configs/config.yaml`:
* `max_test_duration`: 60 seconds
* `max_request_rate`: 100 req/s
* `max_concurrency`: 20 connections
* `request_timeout`: 5.0 seconds

---

## 7. Architecture

```text
dos-tool/
│
├── app/
│   ├── __init__.py           # Package version definition (0.3.0)
│   ├── cli.py                # Typer CLI application (test, load, scenario)
│   ├── config.py             # Pydantic AppConfig model and YAML loader
│   │
│   ├── scenarios/
│   │   ├── __init__.py
│   │   ├── models.py         # Scenario, ScenarioStage, ScenarioResult models
│   │   ├── loader.py         # Scenario directory scanner and YAML parser
│   │   └── runner.py         # Sequential stage orchestration runner
│   │
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── runner.py         # ConnectivityRunner & LoadTestRunner
│   │   ├── worker.py         # Async HTTP worker with semaphore concurrency control
│   │   └── scheduler.py      # RateScheduler with pacing and drift compensation
│   │
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── models.py         # RequestResult and LoadTestReport models
│   │   └── collector.py      # MetricsCollector with percentile calculations
│   │
│   └── safety/
│       ├── __init__.py
│       └── controller.py     # SafetyController multi-parameter validator
│
├── configs/
│   └── config.yaml           # Default safety configuration
│
├── scenarios/
│   ├── ecommerce_product_ramp.yaml
│   └── frontend_load.yaml
│
├── tests/
│   ├── test_cli.py           # CLI invocation & safety rejection tests
│   ├── test_config.py        # Configuration validation tests
│   ├── test_safety.py        # SafetyController limit & URL tests
│   ├── test_http.py          # HTTP connectivity probe tests
│   ├── test_load_engine.py   # LoadTestRunner & async worker tests
│   ├── test_metrics.py       # Metrics collection & percentile calculation tests
│   ├── test_scheduler.py     # RateScheduler tick count & timing tests
│   ├── test_scenarios.py     # Scenario YAML loader & validation tests
│   └── test_scenario_runner.py # ScenarioRunner execution & order tests
│
├── docs/
│   └── superpowers/specs/    # Technical design specifications
│
├── requirements.txt
├── pyproject.toml
├── .gitignore
└── README.md
```

---

## 8. Running Automated Tests

Run the full pytest suite:

```bash
python -m pytest
```

Or with verbose output:

```bash
python -m pytest -v
```

All 78 unit tests use mock transports (`httpx.MockTransport`) and never make outbound requests to external websites.

---

## 9. Roadmap

* [x] **Phase 1 — Project Foundation**
* [x] **Phase 2 — HTTP Load Engine**
* [x] **Phase 3 — Scenario Engine**
* [ ] **Phase 4 — Metrics & Reporting** (JSON/CSV exports, visual charts)
* [ ] **Phase 5 — Web Dashboard** (Real-time telemetry and experiment controls)
* [ ] **Phase 6 — Fault Injection** (Chaos engineering hooks and failure simulation)
* [ ] **Phase 7 — Experiment Framework** (Automated resilience experiments and evaluation)
