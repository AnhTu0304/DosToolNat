"""Reporting generator specifically tailored for Phase 5 Incident & Fault experiments."""

import csv
import html
import json
from pathlib import Path
from typing import Tuple

from app.incidents.models import IncidentResult


def write_incident_json(incident: IncidentResult, output_dir: Path) -> Path:
    """Save full serialized IncidentResult to experiment.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "experiment.json"
    with target.open("w", encoding="utf-8") as f:
        json.dump(incident.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
    return target


def write_incident_csvs(incident: IncidentResult, output_dir: Path) -> Tuple[Path, Path, Path, Path]:
    """Generate stages.csv, latency.csv, faults.csv, and timeline.csv."""
    output_dir.mkdir(parents=True, exist_ok=True)

    stages_path = output_dir / "stages.csv"
    latency_path = output_dir / "latency.csv"
    faults_path = output_dir / "faults.csv"
    timeline_path = output_dir / "timeline.csv"

    # 1. stages.csv (Before, During, After summary rows)
    stage_headers = [
        "experiment_id",
        "phase",
        "total_requests",
        "successful",
        "failed",
        "timeouts",
        "connection_errors",
        "http_2xx",
        "http_3xx",
        "http_4xx",
        "http_5xx",
        "avg_rps",
        "min_latency_ms",
        "avg_latency_ms",
        "p50_latency_ms",
        "p95_latency_ms",
        "p99_latency_ms",
        "max_latency_ms",
        "success_rate",
        "error_rate",
    ]
    with stages_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=stage_headers)
        writer.writeheader()
        phases = [
            ("baseline", incident.before_metrics),
            ("during_fault", incident.during_metrics),
            ("recovery", incident.after_metrics),
        ]
        for phase_name, p in phases:
            writer.writerow({
                "experiment_id": incident.experiment_id,
                "phase": phase_name,
                "total_requests": p.total_requests,
                "successful": p.successful,
                "failed": p.failed,
                "timeouts": p.timeouts,
                "connection_errors": p.connection_errors,
                "http_2xx": p.http_2xx,
                "http_3xx": p.http_3xx,
                "http_4xx": p.http_4xx,
                "http_5xx": p.http_5xx,
                "avg_rps": p.average_rps,
                "min_latency_ms": p.min_latency_ms,
                "avg_latency_ms": p.avg_latency_ms,
                "p50_latency_ms": p.p50_latency_ms,
                "p95_latency_ms": p.p95_latency_ms,
                "p99_latency_ms": p.p99_latency_ms,
                "max_latency_ms": p.max_latency_ms,
                "success_rate": p.success_rate,
                "error_rate": p.error_rate,
            })

    # 2. latency.csv
    latency_headers = ["experiment_id", "timestamp", "stage_number", "latency_ms", "status_code", "success", "error_type"]
    with latency_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=latency_headers)
        writer.writeheader()
        for sample in incident.latency_samples:
            writer.writerow({
                "experiment_id": incident.experiment_id,
                "timestamp": sample.timestamp,
                "stage_number": sample.stage_number,
                "latency_ms": sample.latency_ms if sample.latency_ms is not None else "",
                "status_code": sample.status_code if sample.status_code is not None else "",
                "success": str(sample.success).lower(),
                "error_type": sample.error_type or "",
            })

    # 3. faults.csv
    fault_headers = ["experiment_id", "fault_type", "start_time", "end_time", "duration_seconds", "configuration", "status"]
    with faults_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fault_headers)
        writer.writeheader()
        writer.writerow({
            "experiment_id": incident.experiment_id,
            "fault_type": incident.fault.fault_type,
            "start_time": incident.fault.start_time or "",
            "end_time": incident.fault.end_time or "",
            "duration_seconds": incident.fault.duration_seconds,
            "configuration": json.dumps(incident.fault.configuration),
            "status": incident.fault.status,
        })

    # 4. timeline.csv
    timeline_headers = ["timestamp", "event", "phase", "details"]
    with timeline_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=timeline_headers)
        writer.writeheader()
        for evt in incident.timeline:
            writer.writerow({
                "timestamp": evt.timestamp,
                "event": evt.event,
                "phase": evt.phase,
                "details": json.dumps(evt.details) if evt.details else "",
            })

    return stages_path, latency_path, faults_path, timeline_path


def write_incident_html(incident: IncidentResult, output_dir: Path) -> Path:
    """Generate interactive standalone HTML report featuring Before/During/After and Timeline."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / "report.html"

    b = incident.before_metrics
    d = incident.during_metrics
    a = incident.after_metrics
    f = incident.fault
    r = incident.recovery

    # Helper formatters
    def fmt_num(v): return f"{v:,}" if isinstance(v, (int, float)) else "0"
    def fmt_ms(v): return f"{v:.1f} ms" if isinstance(v, (int, float)) else "N/A"
    def fmt_pct(v): return f"{v:.1f}%" if isinstance(v, (int, float)) else "0.0%"

    timeline_items = []
    for evt in incident.timeline:
        timeline_items.append(f"""
        <div class="timeline-item">
            <div class="t-bullet"></div>
            <div class="t-content">
                <span class="t-time">{evt.timestamp.split('T')[-1][:8] if 'T' in evt.timestamp else evt.timestamp}</span>
                <strong>{html.escape(evt.event.replace('_', ' ').title())}</strong>
                <span class="t-phase">[{html.escape(evt.phase)}]</span>
            </div>
        </div>
        """)

    recovery_color = "#10b981" if r.status == "recovered" else "#ef4444"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Incident Report - {html.escape(incident.scenario_name)}</title>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --surface-color: #151d30;
            --surface-border: #24304f;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #38bdf8;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.5;
            padding: 2rem 1.5rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{
            background: var(--surface-color);
            border: 1px solid var(--surface-border);
            border-radius: 12px;
            padding: 1.5rem 2rem;
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 1rem;
        }}
        .title-block h1 {{
            font-size: 1.75rem;
            color: var(--accent-blue);
            margin-bottom: 0.25rem;
        }}
        .title-block p {{ color: var(--text-secondary); }}
        .meta-tags {{ display: flex; gap: 0.75rem; flex-wrap: wrap; }}
        .tag {{
            background: #0b0f19;
            border: 1px solid var(--surface-border);
            padding: 0.35rem 0.75rem;
            border-radius: 6px;
            font-size: 0.85rem;
            font-family: monospace;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .meta-card {{
            background: var(--surface-color);
            border: 1px solid var(--surface-border);
            border-radius: 8px;
            padding: 1rem 1.25rem;
        }}
        .meta-card span {{
            display: block;
            color: var(--text-secondary);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }}
        .meta-card strong {{ font-size: 1rem; word-break: break-all; }}
        .comparison-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 1.25rem;
            margin-bottom: 2.5rem;
        }}
        @media (max-width: 850px) {{
            .comparison-grid {{ grid-template-columns: 1fr; }}
        }}
        .comp-card {{
            background: var(--surface-color);
            border-radius: 10px;
            border: 1px solid var(--surface-border);
            padding: 1.5rem;
        }}
        .comp-card.baseline {{ border-top: 4px solid var(--accent-blue); }}
        .comp-card.fault {{ border-top: 4px solid var(--accent-red); }}
        .comp-card.recovery {{ border-top: 4px solid var(--accent-green); }}
        .comp-header {{
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 1rem;
            display: flex;
            justify-content: space-between;
        }}
        .stat-line {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            font-size: 0.9rem;
        }}
        .stat-line:last-child {{ border-bottom: none; }}
        .stat-line span:first-child {{ color: var(--text-secondary); }}
        .stat-line span:last-child {{ font-weight: 600; }}
        section {{ margin-bottom: 2.5rem; }}
        section h2 {{
            font-size: 1.25rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--surface-border);
        }}
        .timeline-box {{
            background: var(--surface-color);
            border: 1px solid var(--surface-border);
            border-radius: 10px;
            padding: 1.5rem 2rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        .timeline-item {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        .t-bullet {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--accent-blue);
        }}
        .t-content {{
            font-size: 0.9rem;
            display: flex;
            gap: 0.75rem;
            align-items: center;
        }}
        .t-time {{ color: var(--text-secondary); font-family: monospace; }}
        .t-phase {{ color: var(--text-secondary); font-size: 0.8rem; text-transform: uppercase; }}
        footer {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.8rem;
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--surface-border);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="title-block">
                <h1>Controlled Incident Report</h1>
                <p>{html.escape(incident.description or incident.scenario_name)}</p>
            </div>
            <div class="meta-tags">
                <span class="tag">ID: {html.escape(incident.experiment_id)}</span>
                <span class="tag">Fault: {html.escape(f.fault_type.upper())}</span>
                <span class="tag" style="color: {recovery_color}; font-weight: bold;">Status: {html.escape(r.status.upper())}</span>
            </div>
        </header>

        <div class="meta-grid">
            <div class="meta-card">
                <span>Target</span>
                <strong>{html.escape(incident.target)}</strong>
            </div>
            <div class="meta-card">
                <span>Fault Duration</span>
                <strong>{f.duration_seconds:.1f} s</strong>
            </div>
            <div class="meta-card">
                <span>Recovery Time</span>
                <strong style="color: {recovery_color};">{f"{r.recovery_duration_seconds:.1f} s" if r.recovery_duration_seconds is not None else "N/A"}</strong>
            </div>
            <div class="meta-card">
                <span>Total Duration</span>
                <strong>{incident.total_duration_seconds:.1f} s</strong>
            </div>
        </div>

        <section>
            <h2>Comparative Incident Metrics (Before / During / After)</h2>
            <div class="comparison-grid">
                <!-- 1. BASELINE -->
                <div class="comp-card baseline">
                    <div class="comp-header">
                        <span>1. Baseline (Before)</span>
                    </div>
                    <div class="stat-line"><span>Total Requests</span><span>{fmt_num(b.total_requests)}</span></div>
                    <div class="stat-line"><span>Average RPS</span><span>{b.average_rps:.1f}</span></div>
                    <div class="stat-line"><span>P50 Latency</span><span>{fmt_ms(b.p50_latency_ms)}</span></div>
                    <div class="stat-line"><span>P95 Latency</span><span>{fmt_ms(b.p95_latency_ms)}</span></div>
                    <div class="stat-line"><span>P99 Latency</span><span>{fmt_ms(b.p99_latency_ms)}</span></div>
                    <div class="stat-line"><span>Success Rate</span><span style="color: #10b981;">{fmt_pct(b.success_rate)}</span></div>
                    <div class="stat-line"><span>Error Rate</span><span>{fmt_pct(b.error_rate)}</span></div>
                    <div class="stat-line"><span>HTTP 5xx</span><span>{fmt_num(b.http_5xx)}</span></div>
                </div>

                <!-- 2. DURING FAULT -->
                <div class="comp-card fault">
                    <div class="comp-header">
                        <span>2. Fault (During)</span>
                    </div>
                    <div class="stat-line"><span>Total Requests</span><span>{fmt_num(d.total_requests)}</span></div>
                    <div class="stat-line"><span>Average RPS</span><span>{d.average_rps:.1f}</span></div>
                    <div class="stat-line"><span>P50 Latency</span><span>{fmt_ms(d.p50_latency_ms)}</span></div>
                    <div class="stat-line"><span>P95 Latency</span><span>{fmt_ms(d.p95_latency_ms)}</span></div>
                    <div class="stat-line"><span>P99 Latency</span><span>{fmt_ms(d.p99_latency_ms)}</span></div>
                    <div class="stat-line"><span>Success Rate</span><span style="color: {'#ef4444' if d.error_rate > 5 else '#10b981'};">{fmt_pct(d.success_rate)}</span></div>
                    <div class="stat-line"><span>Error Rate</span><span style="color: {'#ef4444' if d.error_rate > 0 else 'inherit'};">{fmt_pct(d.error_rate)}</span></div>
                    <div class="stat-line"><span>HTTP 5xx</span><span style="color: {'#ef4444' if d.http_5xx > 0 else 'inherit'};">{fmt_num(d.http_5xx)}</span></div>
                </div>

                <!-- 3. RECOVERY -->
                <div class="comp-card recovery">
                    <div class="comp-header">
                        <span>3. Recovery (After)</span>
                    </div>
                    <div class="stat-line"><span>Total Requests</span><span>{fmt_num(a.total_requests)}</span></div>
                    <div class="stat-line"><span>Average RPS</span><span>{a.average_rps:.1f}</span></div>
                    <div class="stat-line"><span>P50 Latency</span><span>{fmt_ms(a.p50_latency_ms)}</span></div>
                    <div class="stat-line"><span>P95 Latency</span><span>{fmt_ms(a.p95_latency_ms)}</span></div>
                    <div class="stat-line"><span>P99 Latency</span><span>{fmt_ms(a.p99_latency_ms)}</span></div>
                    <div class="stat-line"><span>Success Rate</span><span style="color: #10b981;">{fmt_pct(a.success_rate)}</span></div>
                    <div class="stat-line"><span>Error Rate</span><span>{fmt_pct(a.error_rate)}</span></div>
                    <div class="stat-line"><span>HTTP 5xx</span><span>{fmt_num(a.http_5xx)}</span></div>
                </div>
            </div>
        </section>

        <section>
            <h2>Chronological Lifecycle Timeline</h2>
            <div class="timeline-box">
                {"".join(timeline_items)}
            </div>
        </section>

        <footer>
            Generated by <strong>dos-tool</strong> &bull; Controlled Load &amp; Resilience Testing Framework (Phase 5)
        </footer>
    </div>
</body>
</html>
"""
    report_file.write_text(html_content, encoding="utf-8")
    return report_file


class IncidentRecorder:
    """Manages the creation of output folders and multi-format report export for incidents."""

    def __init__(self, output_base_dir: Path = Path("reports")):
        self.output_base_dir = Path(output_base_dir)

    def record(self, incident: IncidentResult) -> Path:
        """Create target directory reports/<scenario_name>/<experiment_id>/ and save all 6 reports."""
        target_dir = self.output_base_dir / incident.scenario_name / incident.experiment_id
        target_dir.mkdir(parents=True, exist_ok=True)

        write_incident_json(incident, target_dir)
        write_incident_csvs(incident, target_dir)
        write_incident_html(incident, target_dir)

        return target_dir
