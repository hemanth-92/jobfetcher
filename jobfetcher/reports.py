"""Generate human-friendly job listing reports with clickable links and filters."""
from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any, Iterable, List, Optional, Sequence

import pandas as pd

from .paths import ensure_parent_dir

LINK_COLUMNS = [
    "match_score",
    "matched_skills",
    "title",
    "company",
    "location",
    "site",
    "source_location",
    "source_query",
    "is_fortune_500",
    "is_mid_level",
    "mid_level_score",
    "est_min_years",
    "est_max_years",
    "in_experience_band",
    "is_profile_match",
    "is_remote",
    "job_url",
]


def _select_link_columns(df: pd.DataFrame) -> pd.DataFrame:
    columns = [column for column in LINK_COLUMNS if column in df.columns]
    return df[columns].copy()


def _unique_sorted(values: Iterable[Any]) -> List[str]:
    items = sorted({str(v).strip() for v in values if pd.notna(v) and str(v).strip()})
    return items


def _bool_attr(value: Any) -> str:
    if isinstance(value, str):
        return "1" if value.strip().lower() in {"1", "true", "yes"} else "0"
    try:
        if pd.isna(value):
            return "0"
    except (TypeError, ValueError):
        pass
    return "1" if bool(value) else "0"


def _option_tags(values: List[str]) -> str:
    return "\n".join(
        f'<option value="{html.escape(value, quote=True)}">{html.escape(value)}</option>'
        for value in values
    )


def write_jobs_html(
    df: pd.DataFrame,
    path: str,
    default_min_years: int = 2,
    default_max_years: int = 4,
    default_mid_level: bool = True,
    profile_skills: Optional[Sequence[str]] = None,
) -> None:
    """Write an HTML table with clickable job title links and client-side filters."""
    ensure_parent_dir(path)
    rows = _select_link_columns(df)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    has_profile = "is_profile_match" in rows.columns
    has_fortune = "is_fortune_500" in rows.columns
    has_remote = "is_remote" in rows.columns
    has_source_query = "source_query" in rows.columns
    has_source_location = "source_location" in rows.columns
    has_match = "match_score" in rows.columns
    has_matched_skills = "matched_skills" in rows.columns
    has_band = "in_experience_band" in rows.columns

    sites = _unique_sorted(rows["site"]) if "site" in rows.columns else []
    source_locations = (
        _unique_sorted(rows["source_location"]) if has_source_location else []
    )
    source_queries = _unique_sorted(rows["source_query"]) if has_source_query else []
    profile_skills = list(profile_skills or [])

    table_rows: List[str] = []
    for _, row in rows.iterrows():
        title_raw = str(row.get("title", "") or "")
        company_raw = str(row.get("company", "") or "")
        location_raw = str(row.get("location", "") or "")
        site_raw = str(row.get("site", "") or "")
        source_loc_raw = str(row.get("source_location", "") or "") if has_source_location else ""
        source_query_raw = str(row.get("source_query", "") or "") if has_source_query else ""
        matched_skills_raw = str(row.get("matched_skills", "") or "") if has_matched_skills else ""
        url = html.escape(str(row.get("job_url", "") or ""), quote=True)

        years = row.get("est_min_years")
        years_num = ""
        years_display = "—"
        if pd.notna(years):
            try:
                years_int = int(years)
                years_num = str(years_int)
                years_display = str(years_int)
            except (TypeError, ValueError):
                years_display = html.escape(str(years))

        mid_level = _bool_attr(row.get("is_mid_level"))
        fortune = _bool_attr(row.get("is_fortune_500")) if has_fortune else ""
        profile = _bool_attr(row.get("is_profile_match")) if has_profile else ""
        remote = _bool_attr(row.get("is_remote")) if has_remote else ""
        in_band = _bool_attr(row.get("in_experience_band")) if has_band else ""

        match_score_raw = row.get("match_score") if has_match else ""
        match_score_num = ""
        match_score_display = "—"
        if has_match and pd.notna(match_score_raw):
            try:
                match_score_num = f"{float(match_score_raw):.1f}"
                match_score_display = match_score_num
            except (TypeError, ValueError):
                match_score_display = html.escape(str(match_score_raw))

        search_blob = " ".join(
            [
                title_raw,
                company_raw,
                location_raw,
                site_raw,
                source_loc_raw,
                source_query_raw,
                matched_skills_raw,
            ]
        ).lower()

        attrs = {
            "data-title": title_raw.lower(),
            "data-company": company_raw.lower(),
            "data-location": location_raw.lower(),
            "data-site": site_raw,
            "data-source-location": source_loc_raw,
            "data-source-query": source_query_raw,
            "data-years": years_num,
            "data-mid": mid_level,
            "data-match": match_score_num,
            "data-skills": matched_skills_raw.lower(),
            "data-search": search_blob,
        }
        if has_fortune:
            attrs["data-fortune"] = fortune
        if has_profile:
            attrs["data-profile"] = profile
        if has_remote:
            attrs["data-remote"] = remote
        if has_band:
            attrs["data-band"] = in_band

        attr_str = " ".join(
            f'{key}="{html.escape(str(value), quote=True)}"' for key, value in attrs.items()
        )

        cells: List[str] = []
        if has_match:
            cells.append(f'<td class="col-match">{html.escape(match_score_display)}</td>')
        cells.extend(
            [
                f'<td class="col-title"><a href="{url}" target="_blank" rel="noopener noreferrer">'
                f"{html.escape(title_raw)}</a></td>",
                f'<td class="col-company">{html.escape(company_raw)}</td>',
                f'<td class="col-location">{html.escape(location_raw)}</td>',
            ]
        )
        if has_source_location:
            cells.append(
                f'<td class="col-source-location">{html.escape(source_loc_raw)}</td>'
            )
        cells.extend(
            [
                f'<td class="col-site">{html.escape(site_raw)}</td>',
                f'<td class="col-years">{html.escape(years_display)}</td>',
                f'<td class="col-mid">{"Yes" if mid_level == "1" else "No"}</td>',
            ]
        )
        if has_band:
            cells.append(f'<td class="col-band">{"Yes" if in_band == "1" else "No"}</td>')
        if has_matched_skills:
            cells.append(
                f'<td class="col-skills">{html.escape(matched_skills_raw)}</td>'
            )
        if has_fortune:
            cells.append(f'<td class="col-fortune">{"Yes" if fortune == "1" else "No"}</td>')
        if has_remote:
            cells.append(f'<td class="col-remote">{"Yes" if remote == "1" else "No"}</td>')
        if has_profile:
            cells.append(f'<td class="col-profile">{"Yes" if profile == "1" else "No"}</td>')
        if has_source_query:
            cells.append(
                f'<td class="col-source-query">{html.escape(source_query_raw)}</td>'
            )

        table_rows.append(f"<tr {attr_str}>" + "".join(cells) + "</tr>")

    headers: List[str] = []
    if has_match:
        headers.append("Match")
    headers.extend(["Title", "Company", "Location"])
    if has_source_location:
        headers.append("Search location")
    headers.extend(["Site", "Min years", "Mid-level"])
    if has_band:
        headers.append(f"{default_min_years}–{default_max_years}y band")
    if has_matched_skills:
        headers.append("Your skills")
    if has_fortune:
        headers.append("Fortune 500")
    if has_remote:
        headers.append("Remote")
    if has_profile:
        headers.append("Profile match")
    if has_source_query:
        headers.append("Search term")

    col_count = len(headers)
    header_html = "\n".join(f"        <th>{html.escape(h)}</th>" for h in headers)
    body = (
        "\n".join(table_rows)
        if table_rows
        else f"<tr><td colspan='{col_count}'>No jobs found.</td></tr>"
    )

    site_options = _option_tags(sites)
    source_location_options = _option_tags(source_locations)
    source_query_options = _option_tags(source_queries)

    feature_flags = {
        "hasSourceLocation": has_source_location,
        "hasSourceQuery": has_source_query,
        "hasFortune": has_fortune,
        "hasRemote": has_remote,
        "hasProfile": has_profile,
        "hasMatch": has_match,
        "hasBand": has_band,
        "total": int(len(rows)),
        "defaultMinYears": default_min_years,
        "defaultMaxYears": default_max_years,
        "defaultMidLevel": bool(default_mid_level),
        "profileSkills": profile_skills,
        "storageKey": "jobfetcher.filters.v2",
        "softMode": True,
    }

    defaults_json = json.dumps(
        {
            "minYears": default_min_years,
            "maxYears": default_max_years,
            "mid": "1" if default_mid_level else "",
            "band": "1",
            "profile": "",
        }
    )
    profile_skills_json = json.dumps(profile_skills)

    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Job Market Listings</title>
  <style>
    :root {{
      --bg: #f1f5f9;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
      --accent: #2563eb;
      --accent-hover: #1d4ed8;
      --accent-soft: #dbeafe;
      --secondary: #f1f5f9;
      --secondary-border: #cbd5e1;
      --shadow: 0 1px 2px rgba(15, 23, 42, 0.05), 0 10px 28px rgba(15, 23, 42, 0.07);
      --radius: 12px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: Inter, "Segoe UI", system-ui, -apple-system, sans-serif;
      margin: 0;
      color: var(--text);
      background: var(--bg);
      line-height: 1.45;
    }}
    .wrap {{ max-width: 1480px; margin: 0 auto; padding: 1.25rem 1.5rem 2rem; }}
    .page-header {{
      display: flex;
      flex-wrap: wrap;
      align-items: flex-end;
      justify-content: space-between;
      gap: 0.75rem 1.5rem;
      margin-bottom: 1rem;
    }}
    .page-header h1 {{
      margin: 0;
      font-size: 1.65rem;
      letter-spacing: -0.02em;
    }}
    .page-header .meta {{
      margin: 0.35rem 0 0;
      color: var(--muted);
      font-size: 0.92rem;
      max-width: 52rem;
    }}
    .panel {{
      position: sticky;
      top: 0.5rem;
      z-index: 30;
      background: rgba(255, 255, 255, 0.97);
      backdrop-filter: blur(10px);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: var(--shadow);
      margin-bottom: 1rem;
      overflow: hidden;
    }}
    .panel-section {{
      padding: 0.9rem 1rem;
      border-bottom: 1px solid var(--border);
    }}
    .panel-section:last-child {{ border-bottom: 0; }}
    .section-label {{
      display: block;
      margin: 0 0 0.55rem;
      font-size: 0.72rem;
      font-weight: 700;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .search-row {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 0.65rem;
    }}
    .search-row input[type="text"] {{
      width: 100%;
      min-height: 44px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.65rem 0.9rem;
      font: inherit;
      font-size: 0.98rem;
      background: #fff;
      color: var(--text);
    }}
    .filters-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 0.75rem 0.85rem;
    }}
    .field {{
      display: flex;
      flex-direction: column;
      gap: 0.28rem;
      min-width: 0;
    }}
    .field label {{
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.04em;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .field input[type="number"],
    .field select {{
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.45rem 0.65rem;
      font: inherit;
      font-size: 0.92rem;
      background: #fff;
      color: var(--text);
    }}
    input:focus, select:focus {{
      outline: 2px solid var(--accent-soft);
      border-color: var(--accent);
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem 1rem;
    }}
    .btn-group {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.5rem;
    }}
    .btn-group.primary-actions {{
      gap: 0.55rem;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.35rem;
      min-height: 40px;
      padding: 0.5rem 0.95rem;
      border: 1px solid transparent;
      border-radius: 10px;
      font: inherit;
      font-size: 0.9rem;
      font-weight: 600;
      line-height: 1.1;
      white-space: nowrap;
      cursor: pointer;
      transition: background 0.12s ease, border-color 0.12s ease, transform 0.05s ease;
    }}
    .btn:active {{ transform: translateY(1px); }}
    .btn-primary {{
      background: var(--accent);
      color: #fff;
    }}
    .btn-primary:hover {{ background: var(--accent-hover); }}
    .btn-secondary {{
      background: var(--secondary);
      color: var(--text);
      border-color: var(--secondary-border);
    }}
    .btn-secondary:hover {{ background: #e2e8f0; }}
    .btn-ghost {{
      background: transparent;
      color: var(--muted);
      border-color: var(--border);
    }}
    .btn-ghost:hover {{
      background: #f8fafc;
      color: var(--text);
    }}
    .stats-bar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.65rem 1rem;
      margin: 0 0 0.9rem;
      color: var(--muted);
      font-size: 0.92rem;
    }}
    .stats-bar strong {{ color: var(--text); }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      background: var(--accent-soft);
      color: #1e3a8a;
      border-radius: 999px;
      padding: 0.28rem 0.75rem;
      font-size: 0.86rem;
      font-weight: 700;
    }}
    .filter-summary {{
      min-height: 1.2em;
      color: var(--muted);
    }}
    .table-wrap {{
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: var(--card);
      box-shadow: var(--shadow);
      max-height: calc(100vh - 340px);
    }}
    table {{
      border-collapse: separate;
      border-spacing: 0;
      width: 100%;
      min-width: 1100px;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 0.65rem 0.75rem;
      text-align: left;
      vertical-align: top;
      font-size: 0.92rem;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #f8fafc;
      z-index: 5;
      cursor: pointer;
      user-select: none;
      white-space: nowrap;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      color: #475569;
    }}
    th:hover {{ background: #eef2ff; color: #1e3a8a; }}
    th .sort {{ color: var(--muted); font-size: 0.72rem; margin-left: 0.25rem; }}
    tr:nth-child(even) td {{ background: #fafbfc; }}
    tr:hover td {{ background: #f0f7ff; }}
    tr.hidden {{ display: none; }}
    a {{ color: var(--accent); text-decoration: none; font-weight: 600; }}
    a:hover {{ text-decoration: underline; }}
    .empty {{ display: none; padding: 2.5rem 1rem; text-align: center; color: var(--muted); }}
    .empty.show {{ display: block; }}
    .col-match {{ font-weight: 700; color: #1d4ed8; white-space: nowrap; }}
    .col-skills {{ color: #334155; font-size: 0.85rem; max-width: 220px; }}
    @media (max-width: 1100px) {{
      .filters-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}
    @media (max-width: 800px) {{
      .wrap {{ padding: 1rem; }}
      .filters-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .toolbar {{ flex-direction: column; align-items: stretch; }}
      .btn-group {{ width: 100%; }}
      .btn {{ flex: 1 1 auto; }}
      .table-wrap {{ max-height: none; }}
      .panel {{ position: static; }}
    }}
    @media (max-width: 520px) {{
      .filters-grid {{ grid-template-columns: 1fr; }}
      .btn-group {{ flex-direction: column; }}
      .btn {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="page-header">
      <div>
        <h1>Job Market Listings</h1>
        <p class="meta">Generated {html.escape(generated_at)} · soft mode keeps all DE jobs · ranked by match score · profile focus {default_min_years}–{default_max_years}y</p>
      </div>
    </header>

    <section class="panel" id="filters">
      <div class="panel-section">
        <span class="section-label">Search</span>
        <div class="search-row">
          <input id="q" type="text" placeholder="Search title, company, skills, location…" autocomplete="off" aria-label="Search jobs">
        </div>
      </div>

      <div class="panel-section">
        <span class="section-label">Filters</span>
        <div class="filters-grid">
          <div class="field">
            <label for="site">Site</label>
            <select id="site">
              <option value="">All sites</option>
              {site_options}
            </select>
          </div>

          {"<div class='field'><label for='sourceLocation'>Search location</label><select id='sourceLocation'><option value=''>All locations</option>" + source_location_options + "</select></div>" if has_source_location else ""}

          {"<div class='field'><label for='sourceQuery'>Search term</label><select id='sourceQuery'><option value=''>All terms</option>" + source_query_options + "</select></div>" if has_source_query else ""}

          <div class="field">
            <label for="mid">Mid-level</label>
            <select id="mid">
              <option value="">All</option>
              <option value="1">Yes</option>
              <option value="0">No</option>
            </select>
          </div>

          {"<div class='field'><label for='band'>" + str(default_min_years) + "–" + str(default_max_years) + "y band</label><select id='band'><option value=''>All</option><option value='1'>In band</option><option value='0'>Stretch only</option></select></div>" if has_band else ""}

          {"<div class='field'><label for='fortune'>Fortune 500</label><select id='fortune'><option value=''>All</option><option value='1'>Yes</option><option value='0'>No</option></select></div>" if has_fortune else ""}

          {"<div class='field'><label for='remote'>Remote</label><select id='remote'><option value=''>All</option><option value='1'>Yes</option><option value='0'>No</option></select></div>" if has_remote else ""}

          {"<div class='field'><label for='profile'>Profile match</label><select id='profile'><option value=''>All</option><option value='1'>Yes</option><option value='0'>No</option></select></div>" if has_profile else ""}

          <div class="field">
            <label for="maxYears">Max years (≤)</label>
            <input id="maxYears" type="number" min="0" max="30" step="1" placeholder="e.g. 4">
          </div>

          <div class="field">
            <label for="minYears">Min years (≥)</label>
            <input id="minYears" type="number" min="0" max="30" step="1" placeholder="e.g. 2">
          </div>

          {"<div class='field'><label for='minMatch'>Min match score</label><input id='minMatch' type='number' step='0.5' placeholder='e.g. 5'></div>" if has_match else ""}
        </div>
      </div>

      <div class="panel-section">
        <div class="toolbar">
          <div class="btn-group primary-actions">
            <button type="button" id="profileBtn" class="btn btn-primary">My profile ({default_min_years}–{default_max_years}y)</button>
            <button type="button" id="showAllBtn" class="btn btn-secondary">Show all</button>
          </div>
          <div class="btn-group">
            <button type="button" id="exportBtn" class="btn btn-secondary">Export CSV</button>
            <button type="button" id="clearBtn" class="btn btn-ghost">Clear filters</button>
          </div>
        </div>
      </div>
    </section>

    <div class="stats-bar">
      <span class="chip">Showing <strong id="visibleCount">{len(rows)}</strong> / <strong id="totalCount">{len(rows)}</strong></span>
      <span class="filter-summary" id="filterSummary"></span>
    </div>

    <div class="table-wrap">
      <table id="jobsTable">
        <thead>
          <tr>
{header_html}
          </tr>
        </thead>
        <tbody>
{body}
        </tbody>
      </table>
      <div class="empty" id="emptyState">No jobs match these filters.</div>
    </div>
  </div>

  <script id="feature-flags" type="application/json">{json.dumps(feature_flags)}</script>
  <script>
    (function () {{
      const flags = JSON.parse(document.getElementById("feature-flags").textContent);
      const defaults = {defaults_json};
      const profileSkills = {profile_skills_json};
      const q = document.getElementById("q");
      const site = document.getElementById("site");
      const sourceLocation = document.getElementById("sourceLocation");
      const sourceQuery = document.getElementById("sourceQuery");
      const mid = document.getElementById("mid");
      const band = document.getElementById("band");
      const fortune = document.getElementById("fortune");
      const remote = document.getElementById("remote");
      const profile = document.getElementById("profile");
      const maxYears = document.getElementById("maxYears");
      const minYears = document.getElementById("minYears");
      const minMatch = document.getElementById("minMatch");
      const clearBtn = document.getElementById("clearBtn");
      const profileBtn = document.getElementById("profileBtn");
      const showAllBtn = document.getElementById("showAllBtn");
      const exportBtn = document.getElementById("exportBtn");
      const visibleCount = document.getElementById("visibleCount");
      const filterSummary = document.getElementById("filterSummary");
      const emptyState = document.getElementById("emptyState");
      const tbody = document.querySelector("#jobsTable tbody");
      const rows = Array.from(tbody.querySelectorAll("tr")).filter(r => r.hasAttribute("data-search"));
      const headers = Array.from(document.querySelectorAll("#jobsTable thead th"));
      const filterEls = [q, site, sourceLocation, sourceQuery, mid, band, fortune, remote, profile, maxYears, minYears, minMatch];

      let sortCol = flags.hasMatch ? 0 : -1;
      let sortAsc = false; // match score desc by default
      let suppressSave = false;

      function val(el) {{
        return el && el.value != null ? String(el.value).trim() : "";
      }}

      function currentState() {{
        return {{
          q: val(q),
          site: val(site),
          sourceLocation: val(sourceLocation),
          sourceQuery: val(sourceQuery),
          mid: val(mid),
          band: val(band),
          fortune: val(fortune),
          remote: val(remote),
          profile: val(profile),
          maxYears: val(maxYears),
          minYears: val(minYears),
          minMatch: val(minMatch),
        }};
      }}

      function applyState(state) {{
        if (!state) return;
        suppressSave = true;
        if (q) q.value = state.q || "";
        if (site) site.value = state.site || "";
        if (sourceLocation) sourceLocation.value = state.sourceLocation || "";
        if (sourceQuery) sourceQuery.value = state.sourceQuery || "";
        if (mid) mid.value = state.mid || "";
        if (band) band.value = state.band || "";
        if (fortune) fortune.value = state.fortune || "";
        if (remote) remote.value = state.remote || "";
        if (profile) profile.value = state.profile || "";
        if (maxYears) maxYears.value = state.maxYears || "";
        if (minYears) minYears.value = state.minYears || "";
        if (minMatch) minMatch.value = state.minMatch || "";
        suppressSave = false;
      }}

      function saveState() {{
        if (suppressSave) return;
        try {{
          localStorage.setItem(flags.storageKey, JSON.stringify(currentState()));
        }} catch (e) {{}}
      }}

      function loadState() {{
        try {{
          const raw = localStorage.getItem(flags.storageKey);
          if (!raw) return null;
          return JSON.parse(raw);
        }} catch (e) {{
          return null;
        }}
      }}

      function applyFilters() {{
        const query = val(q).toLowerCase();
        const siteV = val(site);
        const locV = val(sourceLocation);
        const queryV = val(sourceQuery);
        const midV = val(mid);
        const bandV = val(band);
        const fortuneV = val(fortune);
        const remoteV = val(remote);
        const profileV = val(profile);
        const maxY = val(maxYears) === "" ? null : Number(val(maxYears));
        const minY = val(minYears) === "" ? null : Number(val(minYears));
        const minM = val(minMatch) === "" ? null : Number(val(minMatch));

        let shown = 0;
        for (const row of rows) {{
          const search = row.dataset.search || "";
          const yearsRaw = row.dataset.years;
          const years = yearsRaw === "" || yearsRaw == null ? null : Number(yearsRaw);
          const matchRaw = row.dataset.match;
          const match = matchRaw === "" || matchRaw == null ? null : Number(matchRaw);

          let ok = true;
          if (query && !search.includes(query)) ok = false;
          if (ok && siteV && row.dataset.site !== siteV) ok = false;
          if (ok && locV && row.dataset.sourceLocation !== locV) ok = false;
          if (ok && queryV && row.dataset.sourceQuery !== queryV) ok = false;
          if (ok && midV && row.dataset.mid !== midV) ok = false;
          if (ok && bandV && row.dataset.band !== bandV) ok = false;
          if (ok && fortuneV && row.dataset.fortune !== fortuneV) ok = false;
          if (ok && remoteV && row.dataset.remote !== remoteV) ok = false;
          if (ok && profileV && row.dataset.profile !== profileV) ok = false;
          if (ok && maxY != null && !Number.isNaN(maxY)) {{
            if (years != null && years > maxY) ok = false;
          }}
          if (ok && minY != null && !Number.isNaN(minY)) {{
            if (years != null && years < minY) ok = false;
          }}
          if (ok && minM != null && !Number.isNaN(minM)) {{
            if (match == null || match < minM) ok = false;
          }}

          row.classList.toggle("hidden", !ok);
          if (ok) shown += 1;
        }}

        visibleCount.textContent = String(shown);
        emptyState.classList.toggle("show", shown === 0);

        const parts = [];
        if (query) parts.push('search "' + query + '"');
        if (siteV) parts.push("site=" + siteV);
        if (locV) parts.push("location=" + locV);
        if (queryV) parts.push("term=" + queryV);
        if (midV) parts.push("mid=" + (midV === "1" ? "yes" : "no"));
        if (bandV) parts.push("band=" + (bandV === "1" ? "in" : "stretch"));
        if (fortuneV) parts.push("f500=" + (fortuneV === "1" ? "yes" : "no"));
        if (remoteV) parts.push("remote=" + (remoteV === "1" ? "yes" : "no"));
        if (profileV) parts.push("profile=" + (profileV === "1" ? "yes" : "no"));
        if (maxY != null && !Number.isNaN(maxY)) parts.push("years≤" + maxY);
        if (minY != null && !Number.isNaN(minY)) parts.push("years≥" + minY);
        if (minM != null && !Number.isNaN(minM)) parts.push("match≥" + minM);
        filterSummary.textContent = parts.length ? ("Filters: " + parts.join(" · ")) : "No filters active (showing all kept DE jobs)";
        saveState();
      }}

      function setProfileDefaults() {{
        // Soft focus: surface 2–4y band + mid-level; stretch roles still in file
        applyState({{
          q: "",
          site: "",
          sourceLocation: "",
          sourceQuery: "",
          mid: defaults.mid || "1",
          band: defaults.band || "1",
          fortune: "",
          remote: "",
          profile: "",
          maxYears: String(defaults.maxYears),
          minYears: "",
          minMatch: "",
        }});
        applyFilters();
      }}

      function showAllSoft() {{
        applyState({{
          q: "", site: "", sourceLocation: "", sourceQuery: "", mid: "",
          band: "", fortune: "", remote: "", profile: "",
          maxYears: "", minYears: "", minMatch: ""
        }});
        applyFilters();
      }}

      function clearFilters() {{
        showAllSoft();
        q && q.focus();
      }}

      function cellSortValue(row, colIndex) {{
        const cell = row.children[colIndex];
        if (!cell) return "";
        const text = (cell.innerText || cell.textContent || "").trim().toLowerCase();
        if (text === "—" || text === "-") return "";
        const num = Number(text);
        if (!Number.isNaN(num) && text !== "") return num;
        if (text === "yes") return 1;
        if (text === "no") return 0;
        return text;
      }}

      function sortBy(colIndex, forceAsc) {{
        if (typeof forceAsc === "boolean") {{
          sortCol = colIndex;
          sortAsc = forceAsc;
        }} else if (sortCol === colIndex) {{
          sortAsc = !sortAsc;
        }} else {{
          sortCol = colIndex;
          sortAsc = true;
        }}
        const dir = sortAsc ? 1 : -1;
        const sorted = rows.slice().sort((a, b) => {{
          const av = cellSortValue(a, colIndex);
          const bv = cellSortValue(b, colIndex);
          if (av === "" && bv !== "") return 1;
          if (bv === "" && av !== "") return -1;
          if (av < bv) return -1 * dir;
          if (av > bv) return 1 * dir;
          return 0;
        }});
        for (const row of sorted) tbody.appendChild(row);
        headers.forEach((th, i) => {{
          const marker = th.querySelector(".sort");
          if (!marker) return;
          marker.textContent = i === sortCol ? (sortAsc ? "▲" : "▼") : "";
        }});
      }}

      function exportVisibleCsv() {{
        const visible = rows.filter(r => !r.classList.contains("hidden"));
        if (!visible.length) {{
          alert("No visible rows to export.");
          return;
        }}
        const headerTexts = headers.map(th => th.childNodes[0] ? th.childNodes[0].textContent.trim() : th.textContent.trim());
        const lines = [headerTexts.map(csvEscape).join(",")];
        for (const row of visible) {{
          const vals = Array.from(row.children).map(td => {{
            const link = td.querySelector("a");
            if (link) return link.href + " | " + link.textContent.trim();
            return (td.innerText || td.textContent || "").trim();
          }});
          lines.push(vals.map(csvEscape).join(","));
        }}
        const blob = new Blob([lines.join("\\n")], {{ type: "text/csv;charset=utf-8" }});
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "jobs_filtered.csv";
        a.click();
        URL.revokeObjectURL(a.href);
      }}

      function csvEscape(value) {{
        const text = String(value ?? "");
        if (/[",\\n]/.test(text)) return '"' + text.replace(/"/g, '""') + '"';
        return text;
      }}

      headers.forEach((th, i) => {{
        const span = document.createElement("span");
        span.className = "sort";
        th.appendChild(span);
        th.addEventListener("click", () => sortBy(i));
      }});

      filterEls.forEach(el => {{
        if (!el) return;
        el.addEventListener("input", applyFilters);
        el.addEventListener("change", applyFilters);
      }});
      clearBtn.addEventListener("click", clearFilters);
      profileBtn.addEventListener("click", setProfileDefaults);
      if (showAllBtn) showAllBtn.addEventListener("click", showAllSoft);
      exportBtn.addEventListener("click", exportVisibleCsv);

      const saved = loadState();
      if (saved) {{
        applyState(saved);
      }} else {{
        setProfileDefaults();
      }}
      if (flags.hasMatch) sortBy(0, false);
      applyFilters();
    }})();
  </script>
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
