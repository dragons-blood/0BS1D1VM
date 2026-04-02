"""
HTML report generator for 0BS1D1VM benchmark results.

Generates self-contained HTML files with:
- Model scorecard with grades
- Per-scenario breakdown
- Category radar chart (via inline SVG)
- Campaign timeline (if campaign data available)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


GRADE_COLORS = {
    "S": "#ff00ff",
    "A": "#00cc00",
    "B": "#66cc66",
    "C": "#cccc00",
    "D": "#cc6600",
    "F": "#cc0000",
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>0BS1D1VM Report — {model}</title>
<style>
  :root {{
    --bg: #0a0a0a;
    --card: #141414;
    --border: #2a2a2a;
    --text: #e0e0e0;
    --muted: #888;
    --red: #ff4444;
    --green: #00cc66;
    --yellow: #cccc00;
    --cyan: #00cccc;
    --magenta: #ff00ff;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', monospace;
    padding: 2rem;
    line-height: 1.6;
  }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  .header {{
    text-align: center;
    padding: 2rem 0;
    border-bottom: 2px solid var(--red);
    margin-bottom: 2rem;
  }}
  .header h1 {{
    font-size: 2.5rem;
    color: var(--red);
    letter-spacing: 0.15em;
  }}
  .header .subtitle {{
    color: var(--muted);
    font-size: 0.9rem;
    margin-top: 0.5rem;
  }}
  .scorecard {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 2rem;
    margin-bottom: 2rem;
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 1.5rem;
  }}
  .scorecard .big-grade {{
    grid-column: 1 / -1;
    text-align: center;
    font-size: 6rem;
    font-weight: bold;
    padding: 1rem;
  }}
  .metric {{
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem;
    text-align: center;
  }}
  .metric .label {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; }}
  .metric .value {{ font-size: 1.5rem; font-weight: bold; margin-top: 0.3rem; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 2rem;
  }}
  th, td {{
    padding: 0.75rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border);
  }}
  th {{
    color: var(--red);
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }}
  tr:hover {{ background: rgba(255, 68, 68, 0.05); }}
  .grade {{ font-weight: bold; font-size: 1.1rem; }}
  .pass {{ color: var(--green); }}
  .fail {{ color: var(--red); }}
  .section-title {{
    color: var(--red);
    font-size: 1.3rem;
    margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
  }}
  .bar {{
    height: 8px;
    background: var(--border);
    border-radius: 4px;
    overflow: hidden;
    margin-top: 0.3rem;
  }}
  .bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
  }}
  .footer {{
    text-align: center;
    color: var(--muted);
    font-size: 0.8rem;
    padding: 2rem 0;
    border-top: 1px solid var(--border);
    margin-top: 2rem;
  }}
  .campaign-timeline {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 2rem;
  }}
  .attempt {{
    padding: 0.75rem;
    margin-bottom: 0.5rem;
    border-left: 3px solid var(--border);
    background: var(--bg);
    border-radius: 0 4px 4px 0;
  }}
  .attempt.success {{ border-left-color: var(--green); }}
  .attempt.partial {{ border-left-color: var(--yellow); }}
  .attempt.failed {{ border-left-color: var(--red); }}
  .attempt .meta {{ color: var(--muted); font-size: 0.8rem; }}
  .attempt .payload {{ color: var(--cyan); margin: 0.3rem 0; font-size: 0.85rem; }}
  .attempt .response {{ color: var(--text); font-size: 0.85rem; opacity: 0.8; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>0BS1D1VM</h1>
    <div class="subtitle">Adversarial Range Report — {timestamp}</div>
  </div>

  <div class="scorecard">
    <div class="big-grade" style="color: {grade_color}">{overall_grade}</div>
    <div class="metric">
      <div class="label">Model</div>
      <div class="value" style="font-size: 1rem;">{model}</div>
    </div>
    <div class="metric">
      <div class="label">Overall Score</div>
      <div class="value">{overall_score}</div>
    </div>
    <div class="metric">
      <div class="label">Points</div>
      <div class="value">{points_earned}/{points_possible}</div>
    </div>
    <div class="metric">
      <div class="label">Scenarios</div>
      <div class="value">{scenarios_run}</div>
    </div>
    <div class="metric">
      <div class="label">Objectives Passed</div>
      <div class="value">{objectives_passed}/{objectives_total}</div>
    </div>
    <div class="metric">
      <div class="label">Time</div>
      <div class="value">{elapsed}s</div>
    </div>
  </div>

  <h2 class="section-title">Scenario Results</h2>
  <table>
    <thead>
      <tr>
        <th>Scenario</th>
        <th>Category</th>
        <th>Difficulty</th>
        <th>Score</th>
        <th>Grade</th>
        <th>Points</th>
        <th>Objectives</th>
      </tr>
    </thead>
    <tbody>
      {scenario_rows}
    </tbody>
  </table>

  {category_section}

  {campaign_section}

  <div class="footer">
    Generated by 0BS1D1VM v1.0.0 — The Adversarial Range for AI Agents<br>
    by @elder_plinius • BASI • Fortes fortuna iuvat
  </div>
</div>
</body>
</html>"""


def generate_html_report(
    bench_data: dict,
    campaign_data: dict | None = None,
    output_path: str | Path | None = None,
) -> str:
    """Generate an HTML report from benchmark data.

    Args:
        bench_data: Benchmark JSON data (from `obsidium bench`)
        campaign_data: Optional campaign JSON data
        output_path: Where to save the HTML file. If None, returns HTML string.

    Returns:
        HTML string (and saves to file if output_path provided).
    """
    model = bench_data.get("model", "Unknown")
    overall_score = bench_data.get("overall_score", 0)
    overall_grade = bench_data.get("overall_grade", "F")
    grade_color = GRADE_COLORS.get(overall_grade, "#ffffff")

    # Build scenario rows
    rows = []
    for r in bench_data.get("results", []):
        sc_grade_color = GRADE_COLORS.get(r.get("grade", "F"), "#ffffff")
        score_pct = r.get("score", 0) * 100
        bar_color = "#00cc66" if score_pct >= 70 else "#cccc00" if score_pct >= 40 else "#cc0000"

        obj_passed = sum(1 for o in r.get("objectives", []) if o.get("passed"))
        obj_total = len(r.get("objectives", []))

        rows.append(f"""      <tr>
        <td>{r.get('scenario_name', '')}</td>
        <td>{r.get('category', '')}</td>
        <td>{r.get('difficulty', '')}</td>
        <td>
          {score_pct:.0f}%
          <div class="bar"><div class="bar-fill" style="width: {score_pct}%; background: {bar_color};"></div></div>
        </td>
        <td><span class="grade" style="color: {sc_grade_color}">{r.get('grade', 'F')}</span></td>
        <td>{r.get('points_earned', 0)}/{r.get('points_possible', 0)}</td>
        <td>{obj_passed}/{obj_total}</td>
      </tr>""")

    # Category breakdown
    category_section = ""
    cat_scores: dict[str, list[float]] = {}
    for r in bench_data.get("results", []):
        cat_scores.setdefault(r.get("category", ""), []).append(r.get("score", 0))

    if len(cat_scores) > 1:
        cat_rows = []
        for cat, scores in sorted(cat_scores.items()):
            avg = sum(scores) / len(scores) * 100
            bar_color = "#00cc66" if avg >= 70 else "#cccc00" if avg >= 40 else "#cc0000"
            cat_rows.append(f"""      <tr>
        <td>{cat}</td>
        <td>{len(scores)}</td>
        <td>
          {avg:.0f}%
          <div class="bar"><div class="bar-fill" style="width: {avg}%; background: {bar_color};"></div></div>
        </td>
      </tr>""")

        category_section = f"""
  <h2 class="section-title">Category Breakdown</h2>
  <table>
    <thead>
      <tr><th>Category</th><th>Scenarios</th><th>Avg Score</th></tr>
    </thead>
    <tbody>
      {"".join(cat_rows)}
    </tbody>
  </table>"""

    # Campaign section
    campaign_section = ""
    if campaign_data and campaign_data.get("attempts"):
        attempt_divs = []
        for a in campaign_data["attempts"]:
            score = a.get("score_delta", 0)
            css_class = "success" if score >= 0.7 else "partial" if score >= 0.3 else "failed"
            attempt_divs.append(f"""      <div class="attempt {css_class}">
        <div class="meta">Turn {a.get('turn', '?')} — [{a.get('strategy', '?')}] — Score: {score:.0%}</div>
        <div class="payload">{_escape_html(a.get('payload', '')[:200])}</div>
        <div class="response">{_escape_html(a.get('response', '')[:300])}</div>
      </div>""")

        campaign_section = f"""
  <h2 class="section-title">Campaign Timeline</h2>
  <div class="campaign-timeline">
    <div class="meta" style="margin-bottom: 1rem;">
      Attacker: {campaign_data.get('attacker_model', 'N/A')} |
      Turns: {campaign_data.get('total_turns', 0)} |
      Strategies: {', '.join(campaign_data.get('strategies_used', []))}
    </div>
    {"".join(attempt_divs)}
  </div>"""

    html = HTML_TEMPLATE.format(
        model=model,
        timestamp=bench_data.get("timestamp", datetime.now().isoformat()),
        overall_grade=overall_grade,
        grade_color=grade_color,
        overall_score=f"{overall_score:.1%}",
        points_earned=bench_data.get("total_points_earned", 0),
        points_possible=bench_data.get("total_points_possible", 0),
        scenarios_run=bench_data.get("scenarios_run", 0),
        objectives_passed=bench_data.get("total_objectives_passed", 0),
        objectives_total=bench_data.get("total_objectives", 0),
        elapsed=bench_data.get("elapsed_seconds", 0),
        scenario_rows="\n".join(rows),
        category_section=category_section,
        campaign_section=campaign_section,
    )

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)

    return html


def generate_comparison_html(
    bench_files: list[str | Path],
    output_path: str | Path | None = None,
) -> str:
    """Generate an HTML comparison report from multiple benchmark files.

    Args:
        bench_files: List of paths to benchmark JSON files.
        output_path: Where to save the HTML file.

    Returns:
        HTML string.
    """
    # Load all benchmark data
    benchmarks = []
    for f in bench_files:
        with open(f) as fh:
            benchmarks.append(json.load(fh))

    if not benchmarks:
        return "<html><body>No benchmark data found.</body></html>"

    # Build comparison table
    model_headers = "".join(
        f'<th style="color: var(--cyan);">{b.get("model", "?")}</th>'
        for b in benchmarks
    )

    # Overall scores row
    score_cells = "".join(
        f'<td><span class="grade" style="color: {GRADE_COLORS.get(b.get("overall_grade", "F"), "#fff")}">'
        f'{b.get("overall_grade", "F")}</span> ({b.get("overall_score", 0):.0%})</td>'
        for b in benchmarks
    )

    # Per-scenario comparison
    all_scenarios = set()
    for b in benchmarks:
        for r in b.get("results", []):
            all_scenarios.add(r.get("scenario_id", ""))

    scenario_rows = []
    for sid in sorted(all_scenarios):
        cells = [f'<td style="color: var(--cyan);">{sid}</td>']
        for b in benchmarks:
            found = None
            for r in b.get("results", []):
                if r.get("scenario_id") == sid:
                    found = r
                    break
            if found:
                gc = GRADE_COLORS.get(found.get("grade", "F"), "#fff")
                cells.append(
                    f'<td><span class="grade" style="color: {gc}">'
                    f'{found.get("grade", "F")}</span> ({found.get("score", 0):.0%})</td>'
                )
            else:
                cells.append('<td style="color: var(--muted);">—</td>')
        scenario_rows.append(f"<tr>{''.join(cells)}</tr>")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>0BS1D1VM Model Comparison</title>
<style>
  :root {{ --bg: #0a0a0a; --card: #141414; --border: #2a2a2a; --text: #e0e0e0; --muted: #888; --red: #ff4444; --cyan: #00cccc; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'JetBrains Mono', monospace; padding: 2rem; }}
  .container {{ max-width: 1400px; margin: 0 auto; }}
  h1 {{ color: var(--red); text-align: center; font-size: 2rem; margin-bottom: 0.5rem; }}
  .subtitle {{ text-align: center; color: var(--muted); margin-bottom: 2rem; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--red); font-size: 0.85rem; text-transform: uppercase; }}
  tr:hover {{ background: rgba(255, 68, 68, 0.05); }}
  .grade {{ font-weight: bold; }}
  .footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; padding: 2rem 0; margin-top: 2rem; border-top: 1px solid var(--border); }}
</style>
</head>
<body>
<div class="container">
  <h1>0BS1D1VM</h1>
  <div class="subtitle">Model Comparison — {len(benchmarks)} models</div>

  <table>
    <thead>
      <tr><th>Overall</th>{model_headers}</tr>
    </thead>
    <tbody>
      <tr><td style="color: var(--red);">Grade</td>{score_cells}</tr>
    </tbody>
  </table>

  <h2 style="color: var(--red); margin: 2rem 0 1rem; font-size: 1.2rem;">Per-Scenario Breakdown</h2>
  <table>
    <thead>
      <tr><th>Scenario</th>{model_headers}</tr>
    </thead>
    <tbody>
      {"".join(scenario_rows)}
    </tbody>
  </table>

  <div class="footer">
    Generated by 0BS1D1VM v1.0.0 — @elder_plinius • BASI<br>
    Fortes fortuna iuvat
  </div>
</div>
</body>
</html>"""

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)

    return html


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
