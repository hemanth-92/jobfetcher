import argparse
import csv
import logging
import sys
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional

from .aggregator import (
    aggregate_jobs,
    append_trend_log,
    load_seen_job_urls,
    save_seen_job_urls,
)
from . import analyzer
from .analyzer import AnalyzerOutputs, ProfileFilter
from .paths import DEFAULT_OUTPUT_DIR, OutputPaths, ensure_output_dir, ensure_parent_dir


def _parse_list(value: str) -> List[str]:
    """Parse a comma-separated string into a list of stripped strings."""
    return [s.strip() for s in value.split(",") if s.strip()]


def _build_analyzer_outputs(
    output_paths: OutputPaths,
    links_csv: Optional[str] = None,
    links_html: Optional[str] = None,
    mid_jobs_output: Optional[str] = None,
    mid_jobs_jsonl: Optional[str] = None,
    market_json: Optional[str] = None,
    market_txt: Optional[str] = None,
    keywords_recurrence: Optional[str] = None,
) -> AnalyzerOutputs:
    analyzer_outputs = AnalyzerOutputs.from_output_paths(output_paths)
    overrides = {
        "links_csv": links_csv,
        "links_html": links_html,
        "mid_csv": mid_jobs_output,
        "mid_jsonl": mid_jobs_jsonl,
        "summary_json": market_json,
        "summary_txt": market_txt,
        "recurrence_file": keywords_recurrence,
    }
    return replace(
        analyzer_outputs,
        **{key: value for key, value in overrides.items() if value is not None},
    )


def run_market_analysis(
    output: str,
    analyzer_outputs: AnalyzerOutputs,
    skip_mid_level: bool = False,
    profile: Optional[ProfileFilter] = None,
) -> None:
    """Analyze an existing jobs CSV and write market reports."""
    try:
        enriched = analyzer.run_market_analysis(
            input_csv=output,
            outputs=analyzer_outputs,
            export_mid_level=not skip_mid_level,
            profile=profile,
        )
        if enriched.empty:
            logging.error("No jobs found in %s to analyze.", output)
            sys.exit(1)

        ensure_parent_dir(output)
        enriched.to_csv(output, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        logging.info("Updated %s with market analysis fields.", output)
        logging.info("Open %s in a browser for clickable job links.", analyzer_outputs.links_html)
        logging.info("Market summary written to %s", analyzer_outputs.summary_txt)
        if profile is not None:
            logging.info(
                "Profile matches (if any) saved to %s and %s",
                analyzer_outputs.profile_csv,
                analyzer_outputs.profile_html,
            )
    except (FileNotFoundError, KeyError, ValueError, OSError) as exc:
        logging.error("Failed to run market analysis: %s", exc)
        sys.exit(1)
    except Exception:
        logging.exception("Failed to run market analysis")
        sys.exit(1)


def run_fetcher(
    search_terms: List[str],
    locations: List[str],
    remote_locations: List[str],
    results: int,
    top: int,
    site_names: List[str],
    adzuna_creds: Optional[Dict[str, str]],
    output_paths: OutputPaths,
    analyzer_outputs: AnalyzerOutputs,
    append: bool = False,
    max_workers: int = 4,
    include_seen: bool = False,
    reset_seen: bool = False,
    skip_mid_level: bool = False,
    profile: Optional[ProfileFilter] = None,
) -> None:
    """Execute the job fetching and analysis pipeline."""
    remote_map = {loc: True for loc in remote_locations}
    output = str(output_paths.jobs_csv)
    descriptions_output = str(output_paths.descriptions_txt)
    seen_file = str(output_paths.seen_jobs)
    trend_log = str(output_paths.trend_log)

    jobs = aggregate_jobs(
        search_terms=search_terms,
        locations=locations,
        remote_map=remote_map,
        results_wanted=results,
        top_n=top,
        site_names=site_names,
        adzuna_creds=adzuna_creds,
        append_mode=append,
        max_workers=max_workers,
        include_seen=include_seen,
        reset_seen=reset_seen,
        seen_file=seen_file,
    )

    if jobs.empty:
        return

    ensure_parent_dir(output)
    ensure_parent_dir(descriptions_output)
    if append:
        jobs.to_csv(output, mode="a", header=False, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        logging.info("Appended %d job listings to %s", len(jobs), output)
    else:
        jobs.to_csv(output, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        logging.info("Saved %d job listings to %s", len(jobs), output)

    with open(descriptions_output, "w", encoding="utf-8") as handle:
        for i, (_, row) in enumerate(jobs.iterrows()):
            handle.write(f"JOB #{i + 1}\n")
            handle.write(f"TITLE: {row.get('title')}\n")
            handle.write(f"COMPANY: {row.get('company')}\n")
            handle.write(f"LOCATION: {row.get('location')}\n")
            handle.write(f"SITE: {row.get('site')}\n")
            handle.write(f"URL: {row.get('job_url')}\n")
            handle.write("-" * 40 + "\n")
            handle.write(f"DESCRIPTION:\n{row.get('description')}\n")
            handle.write("=" * 80 + "\n\n")

    seen = load_seen_job_urls(seen_file)
    seen.update(jobs["job_url"].astype(str).tolist())
    save_seen_job_urls(seen, seen_file)
    append_trend_log(jobs, path=trend_log)

    run_market_analysis(
        output=output,
        analyzer_outputs=analyzer_outputs,
        skip_mid_level=skip_mid_level,
        profile=profile,
    )
    logging.info(
        "Key outputs in %s/: jobs_links.csv, jobs.html, profile_matches.html, market_summary.txt",
        output_paths.output_dir,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JobFetcher CLI - Collect job listings and analyze the market"
    )
    parser.add_argument(
        "--search-terms",
        type=_parse_list,
        default=[
            "data engineer",
            "analytics engineer",
            "etl engineer",
            "data pipeline engineer",
            "big data engineer",
            "python data engineer",
        ],
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
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="Max jobs to keep after sorting (0 = keep all fetched jobs)",
    )
    parser.add_argument(
        "--site-names",
        type=_parse_list,
        default=["linkedin", "indeed", "remotive"],
        help="Comma-separated site names to query (linkedin,indeed,remotive,adzuna)",
    )
    parser.add_argument("--adzuna-id", help="Adzuna app_id")
    parser.add_argument("--adzuna-key", help="Adzuna app_key")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where all output files are written",
    )
    parser.add_argument("--output", help="Override full jobs CSV path")
    parser.add_argument("--descriptions-output", help="Override job descriptions text file")
    parser.add_argument("--links-csv", help="Override compact links CSV path")
    parser.add_argument("--links-html", help="Override HTML report path")
    parser.add_argument("--mid-jobs-output", help="Override mid-level CSV path")
    parser.add_argument("--mid-jobs-jsonl", help="Override mid-level JSONL path")
    parser.add_argument("--market-json", help="Override market JSON path")
    parser.add_argument("--market-txt", help="Override market text path")
    parser.add_argument("--keywords-recurrence", help="Override keyword recurrence path")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument("--append", action="store_true", help="Append new jobs to the output file instead of overwriting")
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Max parallel workers for fetching jobs across queries and sites",
    )
    parser.add_argument(
        "--include-seen",
        action="store_true",
        help="Include jobs already tracked in seen_jobs.json",
    )
    parser.add_argument(
        "--reset-seen",
        action="store_true",
        help="Clear seen_jobs.json before fetching",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip fetching and analyze the existing jobs CSV",
    )
    parser.add_argument(
        "--skip-mid-level",
        action="store_true",
        help="Skip writing the optional mid-level subset files",
    )
    parser.add_argument(
        "--profile-skills",
        type=_parse_list,
        help="Candidate skills to match (e.g. snowflake,sql,python)",
    )
    parser.add_argument(
        "--profile-min-years",
        type=int,
        default=2,
        help="Target minimum years of experience for profile matching",
    )
    parser.add_argument(
        "--profile-max-years",
        type=int,
        default=6,
        help="Maximum required years to still count as a profile match",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    output_paths = OutputPaths.for_directory(args.output_dir)
    if args.output:
        output_paths = replace(output_paths, jobs_csv=Path(args.output))
    if args.descriptions_output:
        output_paths = replace(output_paths, descriptions_txt=Path(args.descriptions_output))

    ensure_output_dir(output_paths.output_dir)
    logging.info("Writing outputs to %s/", output_paths.output_dir)

    adzuna_creds = None
    if args.adzuna_id and args.adzuna_key:
        adzuna_creds = {"app_id": args.adzuna_id, "app_key": args.adzuna_key}

    analyzer_outputs = _build_analyzer_outputs(
        output_paths,
        links_csv=args.links_csv,
        links_html=args.links_html,
        mid_jobs_output=args.mid_jobs_output,
        mid_jobs_jsonl=args.mid_jobs_jsonl,
        market_json=args.market_json,
        market_txt=args.market_txt,
        keywords_recurrence=args.keywords_recurrence,
    )

    profile = None
    if args.profile_skills:
        profile = ProfileFilter(
            skills=tuple(skill.lower() for skill in args.profile_skills),
            min_years=args.profile_min_years,
            max_years=args.profile_max_years,
        )

    if args.analyze_only:
        run_market_analysis(
            output=str(output_paths.jobs_csv),
            analyzer_outputs=analyzer_outputs,
            skip_mid_level=args.skip_mid_level,
            profile=profile,
        )
        return

    run_fetcher(
        search_terms=args.search_terms,
        locations=args.locations,
        remote_locations=args.remote_locations,
        results=args.results,
        top=args.top,
        site_names=args.site_names,
        adzuna_creds=adzuna_creds,
        output_paths=output_paths,
        analyzer_outputs=analyzer_outputs,
        append=args.append,
        max_workers=args.workers,
        include_seen=args.include_seen,
        reset_seen=args.reset_seen,
        skip_mid_level=args.skip_mid_level,
        profile=profile,
    )


if __name__ == "__main__":
    main()