# Job Fetcher Status & Usage

## Platform Status

| Platform | Status | Method | Notes |
| :--- | :--- | :--- | :--- |
| **LinkedIn** | ✅ Working | JobSpy / Playwright | Best with `linkedin_fetch_description=True` (slower). |
| **Indeed** | ✅ Working | JobSpy | Most reliable scraper. |
| **Remotive** | ✅ Working | Native API | High quality remote jobs. Integrated into main logic. |
| **Adzuna** | ✅ Working | Native API | Requires `adzuna-id` and `adzuna-key`. |
| **ZipRecruiter** | ❌ Blocked | JobSpy | Cloudflare 403. |
| **Glassdoor** | ❌ Blocked | JobSpy | 403/400 Errors. |
| **Google Jobs** | ❌ Blocked | JobSpy | Structure changed; requires manual query tuning. |

## Usage

### Main Aggregator
The `main.py` is the primary entry point. Default search focuses on India and Global Remote roles.

```bash
uv run jobfetcher \
  --search-terms "software engineer, data engineer" \
  --locations "India, Remote" \
  --site-names "linkedin,indeed,remotive" \
  --results 50 \
  --top 30
```

### Adzuna (with credentials)
```bash
uv run jobfetcher \
  --search-terms "python developer" \
  --site-names "adzuna" \
  --adzuna-id YOUR_ID \
  --adzuna-key YOUR_KEY
```

## Maintenance Notes
- **Reliability**: Jobs are now fetched from each site individually to prevent one source's failure from affecting others.
- **Diversity**: Redundant title filters have been removed to allow for broader search results (e.g., Analytics Engineer, Python Developer).
- **LinkedIn**: If blocked, consider using `scripts/scrape_playwright.py` as a baseline for browser-based scraping.
