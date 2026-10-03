# Phase 5 Technical Design Specification: Controlled Fault / Incident Injection

**Project:** `dos-tool`  
**Phase:** Phase 5 — Controlled Fault / Incident Injection  
**Date:** 2026-10-03  
**Status:** Approved / Implementing  

---

## 1. Overview & Objectives

Phase 5 introduces controlled, reproducible incident and fault injection capabilities into `dos-tool` for resilience evaluation of authorized test applications. The core research question addressed is:
> *When a controlled incident occurs, how do system-level HTTP metrics behave before, during, and after the incident, and how long does it take for the service to recover?*

The experiment lifecycle follows:
```text
BASELINE (Normal Traffic) 
    ↓ 
FAULT INJECTION (Latency / 5xx / Combined) 
    ↓ 
DEGRADATION (Impact Observed) 
    ↓ 
FAULT END (Deactivation & Cleanup) 
    ↓ 
RECOVERY MONITORING (Data-Driven Verification) 
    ↓ 
COMPLETED / PERSISTENCE
```

### Safety & Boundary Constraints:
* Controlled testing only on `localhost`, private environments, staging, and authorized test targets.
* **GET-only** load operations. No mutating HTTP methods.
* **Separation of Concerns:** Load Engine generates HTTP traffic; Fault Controller manages fault activation/deactivation via safe test endpoints/headers; Incident Runner orchestrates the lifecycle; Reporter persists structured metrics.
* **Strict Safety Limits:** Total experiment duration $\le 60$ seconds, max rate $\le 100$ req/s, max concurrency $\le 20$, timeout $\le 5$s.
* **No Coupling to AI Self-Healing:** Independent emission of raw metrics, timeline, and incident logs suitable for downstream AI/ML consumption.

---

## 2. Architecture & Component Design

```text
                           CLI (`dos-tool incident`)
                                      │
                                      ▼
                               IncidentLoader
                         (YAML Parser + Safety Check)
                                      │
                                      ▼
                               IncidentRunner
               (Lifecycle: Baseline -> Fault -> Recovery)
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
      Load Engine              Fault Controller         Recovery Detector
   (HTTP Load Traffic)       (Activate/Deactivate)     (Continuous Monitoring)
   [Reused from Phase 2]     [HTTP Header / Adapter]   [P95, Error Rate, Samples]
            │                         │                         │
            └─────────────────────────┼─────────────────────────┘
                                      ▼
                               IncidentRecorder
                  (experiment.json, stages.csv, latency.csv,
                   faults.csv, timeline.csv, report.html)
```

### 2.1. Supported Fault Types
1. **`latency`**: Introduces an artificial delay in milliseconds (e.g., `delay_ms: 300`).
2. **`http_5xx`**: Injects controlled server error responses at a designated rate (e.g., `error_rate: 0.30`).
3. **`combined`**: Concurrently applies both latency delay and HTTP 5xx error generation.

### 2.2. Fault Controller Mechanism
To ensure zero destructive remote execution on target environments:
* **Dynamic Header Injection:** The Load Engine injects standard test headers (`X-Test-Fault-Type`, `X-Test-Fault-Delay-Ms`, `X-Test-Fault-Error-Rate`) during the active fault window.
* **Test Adapter Endpoint Support:** Optional invocation of safe test hooks (e.g., `POST /test/fault/latency`, `POST /test/fault/reset`).
* **Cleanup Guarantee:** Wrapped in `try...finally` blocks to guarantee fault deactivation on normal completion, unexpected errors, or user `Ctrl+C` interrupts.

### 2.3. Data-Driven Recovery Detection
Recovery is verified against configurable criteria:
* $P95 \le \text{max\_p95\_ms}$
* $\text{error\_rate} \le \text{max\_error\_rate}$
* Sustained for $N$ consecutive evaluation windows (`consecutive_healthy_samples`, default: 3).
* If criteria are met: `recovery_status = "recovered"`, `recovery_duration = t_recovered - t_fault_end`.
* If timeout expires before criteria are met: `recovery_status = "recovery_timeout"`.

---

## 3. Data Models (`app/incidents/models.py`)

* `FaultType`: Enum (`latency`, `http_5xx`, `combined`).
* `FaultConfig`: Configuration model with validation for `delay_ms`, `error_rate`, `duration`, `target_endpoint`.
* `RecoveryCriteria`: Model defining `max_p95_ms`, `max_error_rate`, `consecutive_healthy_samples`.
* `RecoveryConfig`: Model defining `enabled`, `criteria`, `timeout`.
* `IncidentLifecycleState`: Enum tracking the experiment lifecycle.
* `TimelineEvent`: Model capturing `timestamp`, `event`, `phase`, and `details`.
* `IncidentScenario`: Complete YAML schema containing `name`, `target`, `baseline`, `fault`, `recovery`.
* `IncidentResult`: Aggregated result containing `before_metrics`, `during_metrics`, `after_metrics`, `timeline`, `recovery_result`, and `latency_samples`.

---

## 4. Multi-Format Output Artifacts

Generated under `reports/<scenario_name>/<experiment_id>/`:
1. `experiment.json`: Complete serialized `IncidentResult` including metadata, baseline, fault, recovery, raw samples, and timeline.
2. `stages.csv`: Summary metrics across baseline, fault, and recovery phases.
3. `latency.csv`: Raw per-request sample trace including `phase` column (`baseline`, `fault`, `recovery`).
4. `faults.csv`: Record of fault activations, duration, configuration, and cleanup status.
5. `timeline.csv`: High-resolution log of lifecycle events with UTC timestamps.
6. `report.html`: Self-contained, responsive dashboard with Before/During/After comparative cards, timeline steps, and status distribution charts.

---

## 5. CLI Interface (`dos-tool incident`)

* `dos-tool incident list`: List available incident scenarios in `scenarios/`.
* `dos-tool incident show <name>`: Display scenario details (baseline, fault, recovery limits).
* `dos-tool incident run <name> [--output <dir>]`: Execute the incident experiment lifecycle and persist all 6 reports.
