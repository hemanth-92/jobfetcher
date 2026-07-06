"""Generate human-friendly job listing reports with clickable links."""
from __future__ import annotations

import html
from datetime import datetime

import pandas as pd

from .paths import ensure_parent_dir

LINK_COLUMNS = [
    "title",
    "company",
    "location",
    "site",
    "source_location",
    "is_fortune_500",
    "is_mid_level",
    "mid_level_score",
    "est_min_years",
    "est_max_years",
    "job_url",
]


def _select_link_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [column for column in LINK_COLUMNS if column in df.columns]
    return df[columns].copy()


def write_jobs_links_csv(df: pd.DataFrame, path: str) -> None:
    """Write a compact CSV optimized for browsing job links in spreadsheets."""
    ensure_parent_dir(path)
    _select_link_columns(df).to_csv(path, index=False)


def write_jobs_html(df: pd.DataFrame, path: str) -> None:
    """Write an HTML table with clickable job title links."""
    ensure_parent_dir(path)
    rows = _select_link_columns(df)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    table_rows = []
    for _, row in rows.iterrows():
        title = html.escape(str(row.get("title", "")))
        url = html.escape(str(row.get("job_url", "")))
        company = html.escape(str(row.get("company", "")))
        location = html.escape(str(row.get("location", "")))
        site = html.escape(str(row.get("site", "")))
        years = row.get("est_min_years")
        years_display = html.escape(str(int(years))) if pd.notna(years) else "—"
        mid_level = "Yes" if row.get("is_mid_level") else "No"

        table_rows.append(
            "<tr>"
            f'<td><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a></td>'
            f"<td>{company}</td>"
            f"<td>{location}</td>"
            f"<td>{site}</td>"
            f"<td>{years_display}</td>"
            f"<td>{mid_level}</td>"
            "</tr>"
        )

    body = "\n".join(table_rows) if table_rows else "<tr><td colspan='6'>No jobs found.</td></tr>"
    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Job Market Listings</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #1f2937; }}
    h1 {{ margin-bottom: 0.25rem; }}
    p.meta {{ color: #6b7280; margin-top: 0; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1.5rem; }}
    th, td {{ border: 1px solid #d1d5db; padding: 0.6rem 0.75rem; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; }}
    tr:nth-child(even) {{ background: #f9fafb; }}
    a {{ color: #2563eb; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>Job Market Listings</h1>
  <p class="meta">{len(rows)} jobs · generated {generated_at}</p>
  <table>
    <thead>
      <tr>
        <th>Title</th>
        <th>Company</th>
        <th>Location</th>
        <th>Site</th>
        <th>Min Years</th>
        <th>Mid-level</th>
      </tr>
    </thead>
    <tbody>
      {body}
    </tbody>
  </table>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)