# Job Fetcher

Collect **data engineering** job listings, **rank** them for a **2–4 year** profile (soft mode), and browse them in a filterable HTML report.

## What you get

All outputs are written to the `results/` folder by default (3 files max):

| File | Purpose |
|------|---------|
| `results/jobs.csv` | Full job details + `match_score`, years, mid-level, skills |
| `results/jobs.html` | Browseable table with filters, profile preset, CSV export |
| `results/market_summary.json` | Market analysis (skills, sites, top matches) |

Dedup state lives in hidden `results/.seen_jobs.json`.

## Installation

```bash
uv sync
```

## Recommended workflow

```bash
uv run jobfetcher --workers 6 --reset-seen
```

Then open `results/jobs.html`.

### Daily run (new jobs only)

Keeps seen history so you only process listings you have not seen yet:

```bash
bash scripts/daily_run.sh
```

### Re-analyze without fetching

```bash
uv run jobfetcher --analyze-only
```

## Profile defaults (config.json)

| Setting | Default | Meaning |
|---------|---------|---------|
| `experience_min` / `experience_max` | 2 / 4 | Target YoE band (scoring + HTML focus) |
| `my_skills` / `must_skills` / `nice_skills` | python, sql, snowflake… | Personal match score |
| `filter_experience_band` | **false** (soft) | If true, hard-drop jobs outside the band |
| `exclude_senior_titles` | **false** (soft) | If true, hard-drop Senior/Staff/Lead |
| `keep_unknown_years` | true | Unknown YoE still counts as in-band flag |
| `search_terms` | data/analytics/etl engineer | Tighter default queries |

### Soft mode (default)

- **Keeps** all data-engineering titles, including senior and 5+ year posts  
- **Ranks** ideal fits higher via `match_score` (skills + 2–4y + mid-level)  
- Adds `in_experience_band` so you can filter stretch roles without deleting them  
- HTML **My profile (2–4y focus)** applies a soft view; **Show all (soft)** clears it  

Hard mode when you want a short list only:

```bash
uv run jobfetcher --analyze-only --hard-experience-filter --drop-senior
```

Edit `config.json` to tune skills and title patterns.

## Useful flags

- `--experience-min 2 --experience-max 4` — override band used for scoring/flags
- `--hard-experience-filter` — hard-drop outside the YoE band
- `--drop-senior` — hard-drop Senior/Staff/Lead titles
- `--no-experience-filter` / `--keep-senior` — force soft keep (already default)
- `--drop-unknown-years` — with hard filter, drop jobs with no YoE text
- `--profile-skills python,sql,snowflake` — override skill list
- `--reset-seen` — clear duplicate history for a full refresh
- `--analyze-only` — rebuild reports from `results/jobs.csv`

## HTML filters

The report includes:

- Free-text search
- Site / location / search term
- Mid-level, Fortune 500, remote, profile match
- Min/max years and min match score
- **My profile (2–4y)** preset
- Filter state saved in `localStorage`
- **Export CSV** of visible rows
- Click column headers to sort (default: match score)

### View in browser (WSL)

With Live Server on port 5500:

```text
http://localhost:5500/results/jobs.html
```

If needed, use the WSL IP:

```bash
hostname -I | awk '{print $1}'
# example:
# http://172.19.152.131:5500/results/jobs.html
```

Or:

```bash
python3 -m http.server 5501 --directory results
# http://localhost:5501/jobs.html
```

## Pipeline improvements included

1. **Better YoE parsing** — ranges, “at least”, caps outliers (no more “170 years”)
2. **2–4 year band filter** — focused on your experience
3. **Senior title drop** — Staff/Principal/Senior/Lead by default
4. **Personal match score** — must/nice skills from config
5. **HTML UX** — defaults, localStorage, export, score column
6. **Tighter search defaults** — data / analytics / ETL engineer
7. **Smarter dedupe** — strip tracking params + company/title/location fingerprint
8. **Clearer source logs** — ok / empty / failed per board
9. **Daily script** — `scripts/daily_run.sh`
