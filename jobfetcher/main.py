import argparse
import logging
import csv
from typing import List, Dict, Optional

import pandas as pd

from .aggregator import (
    aggregate_jobs,
    append_trend_log,
    load_seen_job_urls,
    save_seen_job_urls,
)
from . import analyzer


def _parse_list(value: str) -> List[str]:
    """Parse a comma-separated string into a list of stripped strings."""
    return [s.strip() for s in value.split(",") if s.strip()]


def run_fetcher(
    search_terms: List[str],
    locations: List[str],
    remote_locations: List[str],
    results: int,
    top: int,
    site_names: List[str],
    adzuna_creds: Optional[Dict[str, str]],
    output: str,
    descriptions_output: str,
    append: bool = False,
) -> None:
    """Execute the job fetching and analysis pipeline."""
    remote_map = {loc: True for loc in remote_locations}

    # 1. Aggregate jobs from multiple sources
    jobs = aggregate_jobs(
        search_terms=search_terms,
        locations=locations,
        remote_map=remote_map,
        results_wanted=results,
        top_n=top,
        site_names=site_names,
        adzuna_creds=adzuna_creds,
        append_mode=append,
    )

    if jobs.empty:
        logging.info("No jobs found for the given queries.")
        return

    # 2. Save detailed results and descriptions
    if append:
        # Append to CSV instead of overwriting
        jobs.to_csv(output, mode='a', header=False, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        logging.info(f"Appended {len(jobs)} full job details to {output}")
    else:
        jobs.to_csv(output, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        logging.info(f"Saved {len(jobs)} full job details to {output}")

    # Only write descriptions file once (overwrite)
    with open(descriptions_output, "w", encoding="utf-8") as f:
        for i, (_, row) in enumerate(jobs.iterrows()):
            f.write(f"JOB #{i+1}\n")
            f.write(f"TITLE: {row.get('title')}\n")
            f.write(f"COMPANY: {row.get('company')}\n")
            f.write(f"LOCATION: {row.get('location')}\n")
            f.write(f"SITE: {row.get('site')}\n")
            f.write(f"URL: {row.get('job_url')}\n")
            f.write("-" * 40 + "\n")
            f.write(f"DESCRIPTION:\n{row.get('description')}\n")
            f.write("=" * 80 + "\n\n")

    # 3. Update tracking and logging
    seen = load_seen_job_urls()
    seen.update(jobs["job_url"].astype(str).tolist())
    save_seen_job_urls(seen)
    append_trend_log(jobs)

    # 4. Run mid-level analysis
    try:
        analyzer.main(input_csv=output)
        analyzer.summarize_requirements(input_csv="mid_jobs.csv")
        logging.info("Completed mid-level extraction and requirements summary.")
    except Exception:
        logging.exception("Failed to run requirement analysis")


def main() -> None:
    parser = argparse.ArgumentParser(description="JobFetcher CLI - Aggregate and analyze job listings")
    parser.add_argument(
        "--search-terms",
        type=_parse_list,
        default=["data engineer", "analytics engineer", "etl engineer", "data pipeline engineer", "big data engineer", "python data engineer"],
        help="Comma-separated search terms",
    )
    parser.add_argument(
        "--locations",
        type=_parse_list,
        default=["India", "Remote"],
        help="Comma-separated locations to search",
    )
    parser.add_argument(
        "--remote-locations",
        type=_parse_list,
        default=["India", "Remote"],
        help="Locations that should be remote-only (comma-separated)",
    )
    parser.add_argument("--results", type=int, default=100, help="Results per query")
    parser.add_argument("--top", type=int, default=30, help="Total top jobs to keep")
    parser.add_argument(
        "--site-names",
        type=_parse_list,
        default=["linkedin", "indeed", "remotive"],
        help="Comma-separated site names to query (linkedin,indeed,remotive,adzuna)",
    )
    parser.add_argument("--adzuna-id", help="Adzuna app_id")
    parser.add_argument("--adzuna-key", help="Adzuna app_key")
    parser.add_argument("--output", default="jobs.csv", help="Output CSV path for links")
    parser.add_argument("--descriptions-output", default="job_descriptions.txt", help="Output for job descriptions")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument("--append", action="store_true", help="Append new jobs to the output file instead of overwriting")

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

    adzuna_creds = None
    if args.adzuna_id and args.adzuna_key:
        adzuna_creds = {"app_id": args.adzuna_id, "app_key": args.adzuna_key}

    run_fetcher(
        search_terms=args.search_terms,
        locations=args.locations,
        remote_locations=args.remote_locations,
        results=args.results,
        top=args.top,
        site_names=args.site_names,
        adzuna_creds=adzuna_creds,
        output=args.output,
        descriptions_output=args.descriptions_output,
        append=args.append,
    )


if __name__ == "__main__":
    main()
