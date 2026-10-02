# dos-tool

Controlled HTTP/DoS testing tool for security and resilience testing of web applications that you own or have explicit permission to test.

---

## 1. Project Overview

`dos-tool` is an independent, controlled HTTP resilience and load testing utility. It is designed to assist system architects, developers, and security professionals in assessing web service availability, failover capabilities, and response characteristics under controlled conditions.

> [!IMPORTANT]
> **Authorized Use Only:** This tool is strictly intended for testing targets that you own or have explicit, documented authorization to test. Unauthorized denial-of-service testing against third-party systems is illegal and violates acceptable use policies.

This project is fully standalone and has no external coupling to external automation or self-healing frameworks.

---

## 2. Current Scope (Phase 1)

This repository currently implements **Phase 1 — Project Foundation ONLY**.

### Included in Phase 1:
* **CLI Foundation**: Powered by Typer and Rich with commands: `test`, `config`, `version`, and `--help`.
* **Configuration Management**: Strongly-typed configuration schema using Pydantic V2 and PyYAML support.
* **Safety Controller**: Pre-execution parameter validation enforcing URL schemes, hosts, timeouts, and rate limits.
* **Logging System**: Sanitized console logging without sensitive headers, credentials, or cookies.
* **Basic HTTP Connectivity Testing**: Single HTTP GET request execution with latency measurement and graceful error handling.
* **Unit Test Suite**: 43 automated unit tests using pytest and mock HTTP transports.
* **Git Configuration**: Clean repository setup with appropriate `.gitignore`.

> [!NOTE]
> **Explicit Non-Goals:** The high-volume HTTP load engine, concurrent attack workers, distributed requests, and rate-limit evasion mechanisms are **NOT** implemented in Phase 1. They are planned for subsequent phases.

---

## 3. Installation

### Requirements
* Python 3.12+ (tested with Python 3.14)
* Virtual environment recommended

### Windows Setup

```powershell
# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment
.venv\Scripts\activate

# 3. Install dependencies and CLI package
pip install -r requirements.txt
pip install -e .
```

### Linux / macOS Setup

```bash
# 1. Create virtual environment
python3 -m venv .venv

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install dependencies and CLI package
pip install -r requirements.txt
pip install -e .
```

---

## 4. Usage

After activating your virtual environment and installing the package, use the `dos-tool` CLI:

### 1. Show Help Information
```bash
dos-tool --help
```

### 2. Check Version
```bash
dos-tool version
```
*Output:*
```text
dos-tool version 0.1.0 (Phase 1 - Foundation)
```

### 3. View Current Configuration & Safety Limits
```bash
dos-tool config
```
*You can also inspect a custom config file:*
```bash
dos-tool config --path configs/config.yaml
```

### 4. Basic HTTP Connectivity Test
```bash
dos-tool test --target http://localhost:8000
```

*Example Output:*
```text
INFO - Starting connectivity test
INFO - Target: http://localhost:8000
INFO - Response status: 200
INFO - Latency: 42ms

DOS TOOL
------------------------------
Target      : http://localhost:8000
Method      : GET
Status      : 200
Latency     : 42 ms
Result      : SUCCESS
------------------------------
```

*Testing with a custom timeout:*
```bash
dos-tool test --target http://localhost:8000 --timeout 3.0
```

*Enabling debug mode (shows Python tracebacks if an error occurs):*
```bash
dos-tool test --target http://localhost:8000 --debug
```

---

## 5. Architecture

The codebase is structured modularly so that Phase 2 can introduce the asynchronous load engine without rewriting the CLI or configuration layers.

```text
dos-tool/
│
├── app/
│   ├── __init__.py           # Package version definition
│   ├── cli.py                # Typer CLI application and Rich formatting
│   ├── config.py             # Pydantic AppConfig model and YAML loader
│   │
│   ├── engine/
│   │   ├── __init__.py
│   │   └── runner.py         # ConnectivityRunner & ConnectivityResult
│   │
│   ├── scenarios/
│   │   └── __init__.py       # Placeholder for Phase 3
│   │
│   ├── metrics/
│   │   └── __init__.py       # Placeholder for Phase 4
│   │
│   └── safety/
│       ├── __init__.py
│       └── controller.py     # SafetyController & SafetyValidationError
│
├── configs/
│   └── config.yaml           # Default YAML configuration
│
├── scenarios/                # Test scenarios directory
├── reports/                  # Generated reports directory
│
├── tests/
│   ├── __init__.py
│   ├── test_cli.py           # CLI invocation and command tests
│   ├── test_config.py        # Configuration validation tests
│   ├── test_safety.py        # SafetyController limit & URL tests
│   └── test_http.py          # HTTP connectivity tests (mocked transport)
│
├── docs/
│   └── superpowers/specs/    # Technical design specifications
│
├── requirements.txt
├── pyproject.toml
├── .gitignore
└── README.md
```

### Module Responsibilities:
* `app.config`: Defines default safety parameters (e.g. `request_timeout`, `max_test_duration`, `max_request_rate`, `max_concurrency`) and handles YAML serialization/deserialization.
* `app.safety.controller`: Enforces safety boundaries before requests are dispatched (validates URL scheme `http`/`https`, host presence, and limit thresholds).
* `app.engine.runner`: Encapsulates single-request network execution via `httpx.Client`, measures high-resolution latency with `time.perf_counter()`, and handles network errors gracefully without raising unhandled exceptions to the CLI.
* `app.cli`: Implements the user-facing command-line interface, Rich output presentation, exit code control (0 on success, 1 on failure), and logging configuration.

---

## 6. Running Tests

Run the full pytest suite with:

```bash
python -m pytest
```

Or with verbose output:

```bash
python -m pytest -v
```

All network calls in tests use local mock transports (`httpx.MockTransport`) and never make outbound requests to external services.

---

## 7. Roadmap

* [x] **Phase 1 — Foundation** (CLI, Config, Safety Controller, Logging, Connectivity Test)
* [ ] **Phase 2 — HTTP Load Engine** (High-concurrency async HTTP engine, rate limiter, worker pool)
* [ ] **Phase 3 — Scenario Engine** (Configurable attack patterns: Slowloris, burst, ramp-up)
* [ ] **Phase 4 — Metrics & Reporting** (Latency percentiles, p95/p99, error rates, export formats)
* [ ] **Phase 5 — Web Dashboard** (Real-time telemetry and experiment controls)
* [ ] **Phase 6 — Fault Injection** (Chaos engineering hooks and failure simulation)
* [ ] **Phase 7 — Experiment Framework** (Automated resilience experiments and evaluation)
