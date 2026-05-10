# Job Fetcher

Aggregate and analyze job listings from multiple sources (LinkedIn, Indeed, Remotive, Adzuna).

## Features
- **Aggregator**: Concurrently scrapes and fetches jobs from multiple platforms.
- **Analyzer**: Filters for mid-level roles and extracts key requirements/skills.
- **Tracking**: Keeps track of seen job URLs to avoid duplicates across runs.
- **Trends**: Logs job trends and keyword recurrence over time.

## Installation

Ensure you have `uv` installed.

```bash
uv sync
```

## Usage

Run the main fetcher:
```bash
uv run jobfetcher \
  --search-terms "data engineer, software engineer" \
  --locations "India, Remote" \
  --site-names "linkedin,indeed,remotive" \
  --results 50 \
  --top 30
```

Or using python directly:
```bash
python main.py --search-terms "data engineer"
```

## Structure
- `main.py`: Entry point and CLI.
- `jobfetcher/`: Core package.
    - `aggregator.py`: Job collection logic.
    - `analyzer.py`: Post-processing and analysis.
- `scripts/`: Utility scripts (e.g., Playwright scraper).
- `jobs.csv`: Full job details (generated).
- `job_trends.log`: Historical trends (generated).
- `mid_jobs.csv`: Mid-level roles extracted (generated).

## Configuration
Update `jobfetcher/aggregator.py` to modify the list of Fortune 500 companies or other defaults.
