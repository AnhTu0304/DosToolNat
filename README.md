# dos-tool

Controlled HTTP load and resilience testing tool for security and performance testing of web applications that you own or have explicit permission to test.

---

## 1. Project Overview

`dos-tool` is an independent, controlled HTTP resilience and load testing utility. It is designed to assist system architects, developers, and security professionals in assessing web service availability, performance characteristics, and stability under controlled conditions.

> [!IMPORTANT]
> **Authorized Use Only:** This tool is strictly intended for testing targets that you own or have explicit, documented authorization to test. Unauthorized denial-of-service testing against third-party systems is illegal and violates acceptable use policies.

This project is fully standalone and has no dependency on separate AI self-healing or remediation frameworks.

---

## 2. Current Scope

This repository currently implements **Phase 1 (Project Foundation)** and **Phase 2 (Controlled HTTP Load Engine)**.

### Implemented in Phase 1 & Phase 2:
* **CLI Interface**: Powered by Typer and Rich with commands:
  * `dos-tool --help`
  * `dos-tool version`
  * `dos-tool config`
  * `dos-tool test` (Single HTTP connectivity probe)
  * `dos-tool load` (Asynchronous controlled load test)
* **Configuration Management**: Strongly-typed configuration schema using Pydantic V2 and PyYAML support.
* **Safety Controller**: Pre-execution parameter validation enforcing URL schemes, hosts, timeouts, duration, and rate limits. Rejects out-of-boundary parameters before any network traffic is dispatched.
* **Logging System**: Sanitized console logging without sensitive headers, credentials, or cookies.
* **Asynchronous HTTP Load Engine**:
  * Paced request scheduling via `RateScheduler` with drift compensation (avoids traffic bursts).
  * Strict concurrency control via `asyncio.Semaphore`.
  * Telemetry collection: total requests, successes, failures, HTTP status codes (2xx, 3xx, 4xx, 5xx), timeouts, connection errors.
  * High-precision latency percentiles: Min, Max, Average, P50, P95, P99.
  * Achieved RPS vs. Target RPS tracking.
  * Graceful shutdown on `Ctrl+C` with partial metrics compilation.
* **Unit Test Suite**: 58 automated unit tests using pytest and mock HTTP transports.

> [!NOTE]
> **Phase 2 Restrictions:**
> The load engine is strictly **GET-only** to prevent mutating state or ecommerce data.
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

### 1. Show Help Information
```bash
dos-tool --help
dos-tool load --help
```

### 2. Check Version
```bash
dos-tool version
```
*Output:*
```text
dos-tool version 0.2.0 (Phase 2 - Controlled HTTP Load Engine)
```

### 3. View Configuration & Safety Limits
```bash
dos-tool config
```

### 4. Basic HTTP Connectivity Test (Single Request)
```bash
dos-tool test --target http://localhost:3000
```

### 5. Controlled HTTP Load Testing
```bash
dos-tool load --target http://localhost:3000 --rate 10 --concurrency 5 --duration 20
```

*Testing against a safe backend GET endpoint:*
```bash
dos-tool load --target http://localhost:5000/api/products --rate 2 --concurrency 1 --duration 10
```

*Example Terminal Output:*
```text
DOS TOOL - CONTROLLED LOAD TEST
----------------------------------------
Target       : http://localhost:5000/api/products
Method       : GET
Duration     : 10 s
Target Rate  : 2 req/s
Concurrency  : 1
----------------------------------------

Running...

----------------------------------------
LOAD TEST RESULT
----------------------------------------
Total Requests : 20
Successful     : 20
Failed         : 0

HTTP 2xx       : 20
HTTP 3xx       : 0
HTTP 4xx       : 0
HTTP 5xx       : 0

Timeouts       : 0
Connection Err : 0

Average Latency: 6.39 ms
Min Latency    : 3.09 ms
Max Latency    : 39.19 ms
P50 Latency    : 4.62 ms
P95 Latency    : 8.15 ms
P99 Latency    : 32.98 ms

Average RPS    : 1.96
Target RPS     : 2.00

Test Duration  : 10.19 s
----------------------------------------
```

---

## 5. Safety Guardrails & Validation

All executions are validated prior to dispatch. If any parameter exceeds configured safety boundaries, the command is rejected immediately:

```bash
dos-tool load --target http://localhost:3000 --rate 1000 --concurrency 100 --duration 120
```

*Output:*
```text
Safety validation failed.

Requested rate: 1000 req/s
Maximum allowed: 100 req/s

Requested concurrency: 100
Maximum allowed: 20

Requested duration: 120s
Maximum allowed: 60s
```

Default safety limits in `configs/config.yaml`:
* `max_test_duration`: 60 seconds
* `max_request_rate`: 100 req/s
* `max_concurrency`: 20 connections
* `request_timeout`: 5.0 seconds

---

## 6. Architecture

```text
dos-tool/
│
├── app/
│   ├── __init__.py           # Package version definition
│   ├── cli.py                # Typer CLI application (test, load, config, version)
│   ├── config.py             # Pydantic AppConfig model and YAML loader
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
│   ├── scenarios/
│   │   └── __init__.py       # Placeholder for Phase 3
│   │
│   └── safety/
│       ├── __init__.py
│       └── controller.py     # SafetyController multi-parameter validator
│
├── configs/
│   └── config.yaml           # Default safety configuration
│
├── tests/
│   ├── test_cli.py           # CLI invocation & safety rejection tests
│   ├── test_config.py        # Configuration validation tests
│   ├── test_safety.py        # SafetyController limit & URL tests
│   ├── test_http.py          # HTTP connectivity probe tests
│   ├── test_load_engine.py   # LoadTestRunner & async worker tests
│   ├── test_metrics.py       # Metrics collection & percentile calculation tests
│   └── test_scheduler.py     # RateScheduler tick count & timing tests
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

## 7. Running Automated Tests

Run the full pytest suite:

```bash
python -m pytest
```

Or with verbose output:

```bash
python -m pytest -v
```

All 58 unit tests use mock transports (`httpx.MockTransport`) and never make outbound requests to external websites.

---

## 8. Roadmap

* [x] **Phase 1 — Project Foundation**
* [x] **Phase 2 — HTTP Load Engine**
* [ ] **Phase 3 — Scenario Engine** (Configurable attack patterns: Slowloris, burst, ramp-up)
* [ ] **Phase 4 — Metrics & Reporting** (JSON/CSV exports, visual charts)
* [ ] **Phase 5 — Web Dashboard** (Real-time telemetry and experiment controls)
* [ ] **Phase 6 — Fault Injection** (Chaos engineering hooks and failure simulation)
* [ ] **Phase 7 — Experiment Framework** (Automated resilience experiments and evaluation)
