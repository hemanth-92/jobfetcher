import csv
import json
import logging
import re
import time
from collections import Counter
from datetime import datetime
from typing import Iterable, List, Optional, Dict, Any

import requests
import pandas as pd
from jobspy import scrape_jobs
from .models import Job

# Configuration
TREND_LOG_FILE = "job_trends.log"
SEEN_JOBS_FILE = "seen_jobs.json"

def load_config(path: str = "config.json") -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        return {"fortune_500_companies": [], "key_skills": []}

CONFIG = load_config()
FORTUNE_500_COMPANIES = CONFIG.get("fortune_500_companies", [])

logger = logging.getLogger(__name__)


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
    fortune_500_jobs = jobs[jobs.get("is_fortune_500", False)]
    other_jobs = jobs[~jobs.get("is_fortune_500", False)]

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
                from jobspy.util import markdown_converter
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
                from jobspy.util import markdown_converter
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
                "currency": "USD" if country == "us" else "INR",
                "is_remote": "remote" in (job.get("description") or "").lower(),
            })
        return pd.DataFrame(jobs)
    except Exception as e:
        logger.error(f"Adzuna API failed: {e}")
        return pd.DataFrame()


def collect_jobs_for_query(
    search_term: str,
    location: str,
    is_remote_only: bool,
    seen_urls: set,
    results_wanted: int = 50,
    site_names: Optional[List[str]] = None,
    adzuna_creds: Optional[dict] = None,
) -> pd.DataFrame:
    """Collect jobs for a single query (term + location) from all specified sources."""
    site_names = site_names or ["linkedin"]
    frames: List[pd.DataFrame] = []
    
    # Handle each site individually for better isolation and variety
    for site in site_names:
        logger.info(f"Fetching jobs from {site} for '{search_term}' in {location}...")
        if site == "remotive":
            df = fetch_remotive(search_term, limit=results_wanted)
            if not df.empty:
                df["source_query"] = search_term
                df["source_location"] = location
                frames.append(df)
        elif site == "adzuna":
            if adzuna_creds:
                df = fetch_adzuna(
                    search_term, 
                    location, 
                    limit=results_wanted, 
                    app_id=adzuna_creds.get("app_id"), 
                    app_key=adzuna_creds.get("app_key")
                )
                if not df.empty:
                    df["source_query"] = search_term
                    df["source_location"] = location
                    frames.append(df)
        else:
            # JobSpy sites (linkedin, indeed, etc.)
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
                    df["source_query"] = search_term
                    df["source_location"] = location
                    df["source_offset"] = offset
                    frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["job_url"], keep="first")
    combined = combined[~combined["job_url"].isin(seen_urls)]
    return combined


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
) -> pd.DataFrame:
    """Run multiple queries, deduplicate, filter and return a dataframe of top jobs."""
    seen_urls = load_seen_job_urls(seen_file)
    all_frames: List[pd.DataFrame] = []
    remote_map = remote_map or {}

    for location in locations:
        is_remote = remote_map.get(location, False)
        for term in search_terms:
            df = collect_jobs_for_query(
                search_term=term,
                location=location,
                is_remote_only=is_remote,
                seen_urls=seen_urls,
                results_wanted=results_wanted,
                site_names=site_names,
                adzuna_creds=adzuna_creds,
            )
            if isinstance(df, pd.DataFrame) and not df.empty:
                all_frames.append(df)
                # Update seen_urls in memory to avoid duplicates across terms/locations
                seen_urls.update(df["job_url"].astype(str).tolist())

    if not all_frames:
        return pd.DataFrame()

    jobs = pd.concat(all_frames, ignore_index=True)
    jobs = jobs.drop_duplicates(subset=["job_url"], keep="first")

    # Broad filtering for relevant roles
    relevant_keywords = r"data|analytics|etl|software|engineer|developer|devops|backend|ml|pipeline|infrastructure|warehouse"
    jobs = jobs[jobs["title"].str.contains(relevant_keywords, case=False, na=False)]

    # Flag top companies
    pattern = "|".join(re.escape(c) for c in FORTUNE_500_COMPANIES)
    jobs["is_fortune_500"] = jobs["company"].str.contains(pattern, case=False, na=False)

    if append_mode:
        # In append mode, we return all new filtered jobs
        return jobs

    # Sort and pick top N: Fortune 500 first, then by location
    jobs = (
        jobs.sort_values(by=["is_fortune_500", "source_location"], ascending=[False, True])
        .reset_index(drop=True)
        .head(top_n)
    )

    return jobs
