import json
import logging
import re
import time
import warnings
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

import pandas as pd
import requests
from jobspy import scrape_jobs
from jobspy.util import markdown_converter

from .config import load_config
from .dedupe import dedupe_jobs, normalize_job_url
from .models import validate_jobs_dataframe
from .title_filter import filter_data_engineering_jobs

TREND_LOG_FILE = "job_trends.log"
SEEN_JOBS_FILE = "seen_jobs.json"

ADZUNA_COUNTRY_CURRENCY = {
    "us": "USD",
    "in": "INR",
    "gb": "GBP",
    "bd": "BDT",
}

CONFIG = load_config()
FORTUNE_500_COMPANIES = CONFIG.get("fortune_500_companies", [])

logger = logging.getLogger(__name__)


@dataclass
class AggregationStats:
    queries_run: int = 0
    fetched: int = 0
    deduped: int = 0
    seen_skipped: int = 0
    invalid_skipped: int = 0
    title_filtered: int = 0
    sources_ok: int = 0
    sources_failed: int = 0
    final_count: int = 0


def _concat_job_frames(frames: List[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate job frames while avoiding pandas dtype warnings."""
    cleaned = [
        frame.dropna(axis=1, how="all")
        for frame in frames
        if isinstance(frame, pd.DataFrame) and not frame.empty
    ]
    if not cleaned:
        return pd.DataFrame()
    return pd.concat(cleaned, ignore_index=True, sort=False)


def load_seen_job_urls(path: str = SEEN_JOBS_FILE) -> set:
    """Load previously seen job URLs from a JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as seen_file:
            return set(json.load(seen_file))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen_job_urls(seen_urls: Iterable[str], path: str = SEEN_JOBS_FILE) -> None:
    """Save seen job URLs to a JSON file."""
    with open(path, "w", encoding="utf-8") as seen_file:
        json.dump(sorted(set(seen_urls)), seen_file, indent=2)


def scrape_with_retry(
    site_name: List[str],
    search_term: str,
    location: str,
    is_remote_only: bool = False,
    results_wanted: int = 50,
    offset: int = 0,
    max_retries: int = 3,
    backoff_base: int = 2,
) -> pd.DataFrame:
    """Scrape jobs using JobSpy with exponential backoff retry logic."""
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug("Fetching %s jobs in %s (attempt %d)", search_term, location, attempt)
            scrape_params = {
                "site_name": site_name,
                "search_term": search_term,
                "location": location,
                "results_wanted": results_wanted,
                "offset": offset,
            }
            if is_remote_only:
                scrape_params["is_remote"] = True

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=".*`dict` method is deprecated.*",
                    category=DeprecationWarning,
                )
                return scrape_jobs(**scrape_params)
        except Exception as exc:
            logger.warning("Error scraping %s@%s: %s", search_term, location, exc)
            if attempt == max_retries:
                logger.error("Max retries reached for %s@%s", search_term, location)
                return pd.DataFrame()
            wait_time = backoff_base ** attempt
            logger.info("Retrying in %s seconds...", wait_time)
            time.sleep(wait_time)
    return pd.DataFrame()


def extract_trend_keywords(rows: pd.DataFrame, top_n: int = 12) -> List[tuple]:
    """Extract most frequent keywords from job descriptions, excluding common stop words."""
    stop_words = {
        "and", "the", "with", "for", "you", "your", "our", "are", "will", "can",
        "from", "that", "this", "about", "role", "team", "work", "working", "job",
        "experience", "data", "engineer", "engineering", "senior", "manager", "plus",
        "help", "build", "develop", "design", "support", "strong", "skills", "using",
        "based", "remote", "hybrid", "india", "united", "states", "us", "uk",
    }
    word_counts = Counter()
    for text in rows.get("description", pd.Series()).fillna("").astype(str):
        # Match words with at least 3 characters, allowing some special chars for tech terms
        words = re.findall(r"[a-zA-Z][a-zA-Z+.#/-]{2,}", text.lower())
        for word in words:
            if word not in stop_words and not word.isdigit():
                word_counts[word] += 1
    return word_counts.most_common(top_n)


def append_trend_log(jobs: pd.DataFrame, path: str = TREND_LOG_FILE) -> None:
    """Append current job search summary and trends to a log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if "is_fortune_500" in jobs.columns:
        is_fortune_500 = jobs["is_fortune_500"].fillna(False)
    else:
        is_fortune_500 = pd.Series(False, index=jobs.index)
    fortune_500_jobs = jobs[is_fortune_500]
    other_jobs = jobs[~is_fortune_500]

    job_type_counts = jobs.get("job_type", pd.Series()).fillna("unknown").value_counts().to_dict()

    top_keywords = extract_trend_keywords(jobs)
    top_titles = jobs.get("title", pd.Series()).value_counts().head(8)
    top_companies = jobs.get("company", pd.Series()).value_counts().head(8)

    lines = [
        "=" * 80,
        f"Run time: {timestamp}",
        f"Total jobs: {len(jobs)}",
        f"Fortune 500 jobs: {len(fortune_500_jobs)}",
        f"Other companies: {len(other_jobs)}",
        f"USA remote jobs: {len(jobs[jobs.get('source_location') == 'United States'])}",
        f"India jobs: {len(jobs[jobs.get('source_location') == 'India'])}",
        f"Job type mix: {job_type_counts}",
        "",
        "Top titles:",
    ]

    for title, count in top_titles.items():
        lines.append(f"- {title}: {count}")

    lines.extend(["", "Top companies:"])
    for company, count in top_companies.items():
        lines.append(f"- {company}: {count}")

    lines.extend(["", "Top description keywords:"])
    for keyword, count in top_keywords:
        lines.append(f"- {keyword}: {count}")

    lines.extend(["", "Sample jobs:"])
    for _, row in jobs.head(5).iterrows():
        lines.append(
            f"- {row.get('title')} | {row.get('company')} | {row.get('location')} | {row.get('source_location')}"
        )

    lines.append("")

    with open(path, "a", encoding="utf-8") as log_file:
        log_file.write("\n".join(lines))
        log_file.write("\n")


def fetch_remotive(keyword: str, limit: int = 50) -> pd.DataFrame:
    """Fetch jobs from Remotive API."""
    url = "https://remotive.com/api/remote-jobs"
    params = {"search": keyword, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        jobs = []
        for job in data.get("jobs", []):
            # Clean description
            desc = job.get("description", "")
            if desc:
                desc = markdown_converter(desc)

            jobs.append({
                "id": f"rem-{job.get('id')}",
                "site": "remotive",
                "job_url": job.get("url"),
                "title": job.get("title"),
                "company": job.get("company_name"),
                "location": job.get("candidate_required_location") or "Remote",
                "date_posted": job.get("publication_date", "").split("T")[0],
                "description": desc,
                "job_type": job.get("job_type"),
                "is_remote": True,
                "company_logo": job.get("company_logo"),
                "category": job.get("category"),
            })
        return pd.DataFrame(jobs)
    except Exception as e:
        logger.error(f"Remotive API failed: {e}")
        return pd.DataFrame()


def fetch_adzuna(
    keyword: str,
    location: str,
    limit: int = 50,
    app_id: Optional[str] = None,
    app_key: Optional[str] = None
) -> pd.DataFrame:
    """Fetch jobs from Adzuna API."""
    if not app_id or not app_key:
        return pd.DataFrame()
    
    # Adzuna country mapping
    country = "us"
    loc_lower = location.lower()
    if "india" in loc_lower:
        country = "in"
    elif "bangladesh" in loc_lower:
        country = "bd"
    elif "united kingdom" in loc_lower or "uk" in loc_lower:
        country = "gb"
        
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": keyword,
        "where": location,
        "results_per_page": limit,
        "content-type": "application/json"
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        jobs = []
        for job in data.get("results", []):
            salary_min = job.get("salary_min")
            salary_max = job.get("salary_max")
            min_amount = float(salary_min) if salary_min else None
            max_amount = float(salary_max) if salary_max else None

            # Clean description
            desc = job.get("description", "")
            if desc:
                desc = markdown_converter(desc)

            jobs.append({
                "id": f"adz-{job.get('id')}",
                "site": "adzuna",
                "job_url": job.get("redirect_url"),
                "title": job.get("title"),
                "company": job.get("company", {}).get("display_name"),
                "location": job.get("location", {}).get("display_name"),
                "date_posted": job.get("created", "").split("T")[0],
                "description": desc,
                "min_amount": min_amount,
                "max_amount": max_amount,
                "currency": ADZUNA_COUNTRY_CURRENCY.get(country, "USD"),
                "is_remote": "remote" in (job.get("description") or "").lower(),
            })
        return pd.DataFrame(jobs)
    except Exception as e:
        logger.error(f"Adzuna API failed: {e}")
        return pd.DataFrame()


def _fetch_from_site(
    site: str,
    search_term: str,
    location: str,
    is_remote_only: bool,
    results_wanted: int,
    adzuna_creds: Optional[dict],
) -> pd.DataFrame:
    """Fetch jobs from a single site for one search term and location."""
    logger.info("Fetching jobs from %s for '%s' in %s...", site, search_term, location)
    frames: List[pd.DataFrame] = []

    if site == "remotive":
        df = fetch_remotive(search_term, limit=results_wanted)
        if not df.empty:
            frames.append(df)
    elif site == "adzuna":
        if adzuna_creds:
            df = fetch_adzuna(
                search_term,
                location,
                limit=results_wanted,
                app_id=adzuna_creds.get("app_id"),
                app_key=adzuna_creds.get("app_key"),
            )
            if not df.empty:
                frames.append(df)
    else:
        offsets = [0]
        if results_wanted > 50:
            offsets.append(50)

        for offset in offsets:
            df = scrape_with_retry(
                site_name=[site],
                search_term=search_term,
                location=location,
                is_remote_only=is_remote_only,
                results_wanted=results_wanted,
                offset=offset,
            )
            if isinstance(df, pd.DataFrame) and not df.empty:
                df = df.copy()
                df["source_offset"] = offset
                frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = _concat_job_frames(frames)
    combined["source_query"] = search_term
    combined["source_location"] = location
    return combined


def collect_jobs_for_query(
    search_term: str,
    location: str,
    is_remote_only: bool,
    results_wanted: int = 50,
    site_names: Optional[List[str]] = None,
    adzuna_creds: Optional[dict] = None,
    max_workers: int = 4,
) -> pd.DataFrame:
    """Collect jobs for a single query (term + location) from all specified sources."""
    site_names = site_names or ["linkedin"]
    frames: List[pd.DataFrame] = []
    worker_count = max(1, min(max_workers, len(site_names)))

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                _fetch_from_site,
                site,
                search_term,
                location,
                is_remote_only,
                results_wanted,
                adzuna_creds,
            ): site
            for site in site_names
        }
        for future in as_completed(futures):
            site = futures[future]
            try:
                df = future.result()
                if isinstance(df, pd.DataFrame) and not df.empty:
                    frames.append(df)
                    logger.info(
                        "Source ok: %s '%s'@%s → %d jobs",
                        site,
                        search_term,
                        location,
                        len(df),
                    )
                else:
                    logger.warning(
                        "Source empty: %s returned 0 jobs for '%s' in %s",
                        site,
                        search_term,
                        location,
                    )
            except Exception as exc:
                logger.error(
                    "Source failed: %s for '%s' in %s: %s",
                    site,
                    search_term,
                    location,
                    exc,
                )

    if not frames:
        return pd.DataFrame()

    combined = _concat_job_frames(frames)
    return combined.drop_duplicates(subset=["job_url"], keep="first")


def _collect_query_task(
    search_term: str,
    location: str,
    is_remote_only: bool,
    results_wanted: int,
    site_names: Optional[List[str]],
    adzuna_creds: Optional[dict],
    max_workers: int,
) -> pd.DataFrame:
    """Worker wrapper for parallel query collection."""
    return collect_jobs_for_query(
        search_term=search_term,
        location=location,
        is_remote_only=is_remote_only,
        results_wanted=results_wanted,
        site_names=site_names,
        adzuna_creds=adzuna_creds,
        max_workers=max_workers,
    )


def _log_aggregation_summary(stats: AggregationStats, seen_file: str) -> None:
    """Log a breakdown of how many jobs survived each pipeline stage."""
    if stats.final_count:
        logger.info(
            "Aggregation summary: fetched=%d, deduped=%d, seen_skipped=%d, "
            "invalid=%d, title_filtered=%d, final=%d",
            stats.fetched,
            stats.deduped,
            stats.seen_skipped,
            stats.invalid_skipped,
            stats.title_filtered,
            stats.final_count,
        )
        return

    if stats.fetched == 0:
        logger.warning(
            "No jobs returned from any source for %d queries. "
            "Check network connectivity, site availability, or try different search terms.",
            stats.queries_run,
        )
        return

    if stats.seen_skipped == stats.deduped:
        logger.warning(
            "All %d fetched jobs were already tracked in %s. "
            "Use --reset-seen to clear history or --include-seen to allow duplicates.",
            stats.deduped,
            seen_file,
        )
        return

    logger.warning(
        "No jobs left after filtering (fetched=%d, seen_skipped=%d, invalid=%d, title_filtered=%d).",
        stats.fetched,
        stats.seen_skipped,
        stats.invalid_skipped,
        stats.title_filtered,
    )


def aggregate_jobs(
    search_terms: Iterable[str],
    locations: Iterable[str],
    remote_map: Optional[dict] = None,
    results_wanted: int = 50,
    site_names: Optional[List[str]] = None,
    top_n: int = 20,
    seen_file: str = SEEN_JOBS_FILE,
    adzuna_creds: Optional[dict] = None,
    append_mode: bool = False,
    max_workers: int = 4,
    include_seen: bool = False,
    reset_seen: bool = False,
) -> pd.DataFrame:
    """Run multiple queries, deduplicate, filter and return a dataframe of top jobs."""
    stats = AggregationStats()
    if reset_seen:
        save_seen_job_urls([], seen_file)
        logger.info("Cleared seen job history at %s", seen_file)

    seen_urls = load_seen_job_urls(seen_file)
    if seen_urls and not include_seen:
        logger.info("Tracking %d previously seen job URLs in %s", len(seen_urls), seen_file)

    all_frames: List[pd.DataFrame] = []
    remote_map = remote_map or {}
    query_tasks: List[Tuple[str, str, bool]] = [
        (term, location, remote_map.get(location, False))
        for location in locations
        for term in search_terms
    ]
    stats.queries_run = len(query_tasks)
    worker_count = max(1, min(max_workers, len(query_tasks)))

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(
                _collect_query_task,
                term,
                location,
                is_remote,
                results_wanted,
                site_names,
                adzuna_creds,
                max_workers,
            ): (term, location)
            for term, location, is_remote in query_tasks
        }
        for future in as_completed(futures):
            term, location = futures[future]
            try:
                df = future.result()
                if isinstance(df, pd.DataFrame) and not df.empty:
                    all_frames.append(df)
            except Exception as exc:
                logger.error("Failed query '%s' in %s: %s", term, location, exc)

    if not all_frames:
        _log_aggregation_summary(stats, seen_file)
        return pd.DataFrame()

    jobs = _concat_job_frames(all_frames)
    stats.fetched = len(jobs)
    if "job_url" in jobs.columns:
        jobs["job_url"] = jobs["job_url"].map(normalize_job_url)
    before_dedupe = len(jobs)
    jobs = dedupe_jobs(jobs)
    stats.deduped = len(jobs)
    if before_dedupe != stats.deduped:
        logger.info(
            "Deduped jobs: %d → %d (normalized URL + company/title/location)",
            before_dedupe,
            stats.deduped,
        )

    if not include_seen:
        before_seen = len(jobs)
        normalized_seen = {normalize_job_url(url) for url in seen_urls}
        jobs = jobs[~jobs["job_url"].astype(str).map(normalize_job_url).isin(normalized_seen)]
        stats.seen_skipped = before_seen - len(jobs)
        if stats.seen_skipped:
            logger.info("Skipped %d jobs already tracked in %s", stats.seen_skipped, seen_file)

    before_validation = len(jobs)
    jobs = validate_jobs_dataframe(jobs)
    stats.invalid_skipped = before_validation - len(jobs)
    if stats.invalid_skipped:
        logger.info("Dropped %d invalid job records during validation", stats.invalid_skipped)

    if jobs.empty:
        _log_aggregation_summary(stats, seen_file)
        return pd.DataFrame()

    # Keep only data-engineering titles (drop backend/frontend/SWE/analyst/etc.)
    before_title = len(jobs)
    jobs = filter_data_engineering_jobs(jobs)
    stats.title_filtered = before_title - len(jobs)
    if stats.title_filtered:
        logger.info(
            "Filtered out %d non data-engineering titles (kept %d)",
            stats.title_filtered,
            len(jobs),
        )

    if jobs.empty:
        _log_aggregation_summary(stats, seen_file)
        return pd.DataFrame()

    # Flag top companies
    pattern = "|".join(re.escape(c) for c in FORTUNE_500_COMPANIES)
    jobs["is_fortune_500"] = jobs["company"].str.contains(pattern, case=False, na=False)

    if append_mode:
        stats.final_count = len(jobs)
        _log_aggregation_summary(stats, seen_file)
        return jobs

    # Sort by priority; optionally cap to top N (0 keeps all jobs)
    jobs = (
        jobs.sort_values(by=["is_fortune_500", "source_location"], ascending=[False, True])
        .reset_index(drop=True)
    )
    if top_n > 0:
        jobs = jobs.head(top_n)
    stats.final_count = len(jobs)
    _log_aggregation_summary(stats, seen_file)

    return jobs
