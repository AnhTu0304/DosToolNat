"""HTML reporter for generating clean, self-contained experiment reports."""

import html
from pathlib import Path
from app.metrics.models import ExperimentResult


def write_html_report(experiment: ExperimentResult, output_dir: Path) -> Path:
    """Generate a clean, standalone HTML report for the experiment."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / "report.html"

    agg = experiment.aggregate_metrics
    stats = experiment.latency_statistics or {}

    # Format helpers
    def fmt_num(v, default="0"):
        return f"{v:,}" if isinstance(v, (int, float)) and v is not None else default

    def fmt_ms(v):
        return f"{v:.1f} ms" if isinstance(v, (int, float)) and v is not None else "N/A"

    def fmt_pct(v):
        return f"{v:.1f}%" if isinstance(v, (int, float)) and v is not None else "N/A"

    success_color = "#10b981" if agg.error_rate == 0 else "#f59e0b" if agg.error_rate < 10 else "#ef4444"

    # Build stage rows
    stage_rows = []
    for s in experiment.stages:
        stage_rows.append(f"""
        <tr>
            <td style="font-weight: 600; text-align: center;">Stage {s.stage_number}</td>
            <td>{s.target_rate:.0f} req/s</td>
            <td>{s.actual_rps:.1f} req/s</td>
            <td>{s.concurrency}</td>
            <td>{s.duration_seconds:.0f}s</td>
            <td style="font-weight: 600;">{fmt_num(s.total_requests)}</td>
            <td style="color: #10b981;">{fmt_num(s.successful)}</td>
            <td style="color: {'#ef4444' if s.failed > 0 else '#6b7280'};">{fmt_num(s.failed)}</td>
            <td>{fmt_ms(s.avg_latency_ms)}</td>
            <td>{fmt_ms(s.p50_latency_ms)}</td>
            <td>{fmt_ms(s.p95_latency_ms)}</td>
            <td>{fmt_ms(s.p99_latency_ms)}</td>
        </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Experiment Report - {html.escape(experiment.scenario_name)}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --surface-color: #1e293b;
            --surface-border: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.5;
            padding: 2rem 1.5rem;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
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
            font-weight: 700;
            color: #38bdf8;
            margin-bottom: 0.25rem;
        }}
        .title-block p {{
            color: var(--text-secondary);
            font-size: 0.95rem;
        }}
        .meta-tags {{
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
        }}
        .tag {{
            background: #0f172a;
            border: 1px solid var(--surface-border);
            padding: 0.4rem 0.8rem;
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
        .meta-card strong {{
            font-size: 1rem;
            color: var(--text-primary);
            word-break: break-all;
        }}
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 2.5rem;
        }}
        .card {{
            background: var(--surface-color);
            border: 1px solid var(--surface-border);
            border-radius: 10px;
            padding: 1.25rem;
            text-align: center;
        }}
        .card .label {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}
        .card .value {{
            font-size: 1.75rem;
            font-weight: 700;
        }}
        section {{
            margin-bottom: 2.5rem;
        }}
        section h2 {{
            font-size: 1.25rem;
            margin-bottom: 1rem;
            color: #e2e8f0;
            border-bottom: 1px solid var(--surface-border);
            padding-bottom: 0.5rem;
        }}
        .table-responsive {{
            overflow-x: auto;
            border-radius: 8px;
            border: 1px solid var(--surface-border);
            background: var(--surface-color);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            text-align: left;
        }}
        th, td {{
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--surface-border);
        }}
        th {{
            background: #182234;
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .two-cols {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
        }}
        @media (max-width: 768px) {{
            .two-cols {{
                grid-template-columns: 1fr;
            }}
        }}
        .list-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.75rem;
        }}
        .list-item {{
            display: flex;
            justify-content: space-between;
            padding: 0.6rem 0.8rem;
            background: #0f172a;
            border-radius: 6px;
            font-size: 0.85rem;
        }}
        .list-item span:first-child {{
            color: var(--text-secondary);
        }}
        .list-item span:last-child {{
            font-weight: 600;
        }}
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
                <h1>Experiment Report</h1>
                <p>{html.escape(experiment.description or experiment.scenario_name)}</p>
            </div>
            <div class="meta-tags">
                <span class="tag">ID: {html.escape(experiment.experiment_id)}</span>
                <span class="tag">{html.escape(experiment.method)}</span>
            </div>
        </header>

        <div class="meta-grid">
            <div class="meta-card">
                <span>Target URL</span>
                <strong>{html.escape(experiment.target)}</strong>
            </div>
            <div class="meta-card">
                <span>Scenario Name</span>
                <strong>{html.escape(experiment.scenario_name)}</strong>
            </div>
            <div class="meta-card">
                <span>Total Duration</span>
                <strong>{experiment.total_duration_seconds:.1f} s</strong>
            </div>
            <div class="meta-card">
                <span>Execution Time</span>
                <strong>{html.escape(experiment.start_time.split('T')[0] if 'T' in experiment.start_time else experiment.start_time)}</strong>
            </div>
        </div>

        <div class="cards-grid">
            <div class="card">
                <div class="label">Total Requests</div>
                <div class="value">{fmt_num(agg.total_requests)}</div>
            </div>
            <div class="card">
                <div class="label">Success Rate</div>
                <div class="value" style="color: {success_color};">{fmt_pct(agg.success_rate)}</div>
            </div>
            <div class="card">
                <div class="label">Failed Requests</div>
                <div class="value" style="color: {'#ef4444' if agg.failed > 0 else '#94a3b8'};">{fmt_num(agg.failed)}</div>
            </div>
            <div class="card">
                <div class="label">Average RPS</div>
                <div class="value">{agg.average_rps:.1f}</div>
            </div>
            <div class="card">
                <div class="label">P50 Latency</div>
                <div class="value">{fmt_ms(stats.get('p50'))}</div>
            </div>
            <div class="card">
                <div class="label">P95 Latency</div>
                <div class="value">{fmt_ms(stats.get('p95'))}</div>
            </div>
            <div class="card">
                <div class="label">P99 Latency</div>
                <div class="value">{fmt_ms(stats.get('p99'))}</div>
            </div>
        </div>

        <section>
            <h2>Stage Summary</h2>
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th style="text-align: center;">Stage</th>
                            <th>Target Rate</th>
                            <th>Actual RPS</th>
                            <th>Concurrency</th>
                            <th>Duration</th>
                            <th>Total</th>
                            <th>Success</th>
                            <th>Failed</th>
                            <th>Avg Latency</th>
                            <th>P50</th>
                            <th>P95</th>
                            <th>P99</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(stage_rows)}
                    </tbody>
                </table>
            </div>
        </section>

        <div class="two-cols">
            <section>
                <h2>Latency Distribution (All Requests)</h2>
                <div class="list-grid">
                    <div class="list-item"><span>Min Latency</span><span>{fmt_ms(stats.get('min'))}</span></div>
                    <div class="list-item"><span>Average Latency</span><span>{fmt_ms(stats.get('average'))}</span></div>
                    <div class="list-item"><span>P50 Latency</span><span>{fmt_ms(stats.get('p50'))}</span></div>
                    <div class="list-item"><span>P90 Latency</span><span>{fmt_ms(stats.get('p90'))}</span></div>
                    <div class="list-item"><span>P95 Latency</span><span>{fmt_ms(stats.get('p95'))}</span></div>
                    <div class="list-item"><span>P99 Latency</span><span>{fmt_ms(stats.get('p99'))}</span></div>
                    <div class="list-item" style="grid-column: span 2;"><span>Max Latency</span><span>{fmt_ms(stats.get('max'))}</span></div>
                </div>
            </section>

            <section>
                <h2>Status & Error Breakdown</h2>
                <div class="list-grid">
                    <div class="list-item"><span>HTTP 2xx (Success)</span><span style="color: #10b981;">{fmt_num(agg.http_2xx)}</span></div>
                    <div class="list-item"><span>HTTP 3xx (Redirect)</span><span>{fmt_num(agg.http_3xx)}</span></div>
                    <div class="list-item"><span>HTTP 4xx (Client Error)</span><span style="color: {'#ef4444' if agg.http_4xx > 0 else 'inherit'};">{fmt_num(agg.http_4xx)}</span></div>
                    <div class="list-item"><span>HTTP 5xx (Server Error)</span><span style="color: {'#ef4444' if agg.http_5xx > 0 else 'inherit'};">{fmt_num(agg.http_5xx)}</span></div>
                    <div class="list-item"><span>Timeouts</span><span style="color: {'#ef4444' if agg.timeouts > 0 else 'inherit'};">{fmt_num(agg.timeouts)}</span></div>
                    <div class="list-item"><span>Connection Errors</span><span style="color: {'#ef4444' if agg.connection_errors > 0 else 'inherit'};">{fmt_num(agg.connection_errors)}</span></div>
                </div>
            </section>
        </div>

        <footer>
            Generated by <strong>dos-tool</strong> &bull; Controlled Load &amp; Resilience Testing Framework
        </footer>
    </div>
</body>
</html>
"""

    report_file.write_text(html_content, encoding="utf-8")
    return report_file
