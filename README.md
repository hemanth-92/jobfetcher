# Job Fetcher

Collect job listings, browse them through clickable links, and analyze the full job market.

## What you get

All outputs are written to the `results/` folder by default:

| File | Purpose |
|------|---------|
| `results/jobs.html` | **Best for browsing** — clickable job titles |
| `results/jobs_links.csv` | Compact spreadsheet with `job_url` links |
| `results/jobs.csv` | Full job details plus analysis fields |
| `results/market_summary.txt` | Market analysis across **all** jobs |
| `results/market_summary.json` | Same analysis in JSON |
| `results/mid_jobs.csv` | Optional mid-level subset |

## Installation

```bash
uv sync
```

## Recommended workflow

```bash
uv run jobfetcher --workers 6 --reset-seen
```

Then open:
- `results/jobs.html` for clickable links
- `results/market_summary.txt` for market trends

Re-analyze without fetching:

```bash
uv run jobfetcher --analyze-only
```

Use a different output folder:

```bash
uv run jobfetcher --output-dir my-run
```

## Useful flags

- `--output-dir results` — where all files are saved (default: `results`)
- `--top 0` — keep all fetched jobs
- `--reset-seen` — clear duplicate tracking for a fresh fetch
- `--analyze-only` — rebuild reports from `results/jobs.csv`

## Configuration

Edit `config.json` at the project root to update Fortune 500 companies, key skills, and other defaults.