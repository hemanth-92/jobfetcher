import argparse
import csv
import logging
import sys
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional

from .aggregator import (
    aggregate_jobs,
    load_seen_job_urls,
    save_seen_job_urls,
)
from . import analyzer
from .analyzer import AnalyzerOutputs, ProfileFilter
from .config import load_config
from .paths import DEFAULT_OUTPUT_DIR, OutputPaths, ensure_output_dir, ensure_parent_dir

CONFIG = load_config()


def _parse_list(value: str) -> List[str]:
    """Parse a comma-separated string into a list of stripped strings."""
    return [s.strip() for s in value.split(",") if s.strip()]


def _build_analyzer_outputs(
    output_paths: OutputPaths,
    links_html: Optional[str] = None,
    market_json: Optional[str] = None,
) -> AnalyzerOutputs:
    analyzer_outputs = AnalyzerOutputs.from_output_paths(output_paths)
    overrides = {
        "links_html": links_html,
        "summary_json": market_json,
    }
    return replace(
        analyzer_outputs,
        **{key: value for key, value in overrides.items() if value is not None},
    )


def run_market_analysis(
    output: str,
    analyzer_outputs: AnalyzerOutputs,
    profile: Optional[ProfileFilter] = None,
    filter_experience: Optional[bool] = None,
    exclude_senior: Optional[bool] = None,
    experience_min: Optional[int] = None,
    experience_max: Optional[int] = None,
    keep_unknown_years: Optional[bool] = None,
) -> None:
    """Analyze an existing jobs CSV and write market reports."""
    try:
        enriched = analyzer.run_market_analysis(
            input_csv=output,
            outputs=analyzer_outputs,
            profile=profile,
            filter_experience=filter_experience,
            exclude_senior=exclude_senior,
            experience_min=experience_min,
            experience_max=experience_max,
            keep_unknown_years=keep_unknown_years,
        )
        if enriched.empty:
            logging.error("No jobs found in %s to analyze.", output)
            sys.exit(1)

        ensure_parent_dir(output)
        enriched.to_csv(output, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        logging.info("Updated %s with market analysis fields.", output)
        logging.info("Open %s in a browser for clickable job links.", analyzer_outputs.links_html)
        logging.info("Market summary written to %s", analyzer_outputs.summary_json)
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
    profile: Optional[ProfileFilter] = None,
    filter_experience: Optional[bool] = None,
    exclude_senior: Optional[bool] = None,
    experience_min: Optional[int] = None,
    experience_max: Optional[int] = None,
    keep_unknown_years: Optional[bool] = None,
) -> None:
    """Execute the job fetching and analysis pipeline."""
    remote_map = {loc: True for loc in remote_locations}
    output = str(output_paths.jobs_csv)
    seen_file = str(output_paths.seen_jobs)

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
    if append:
        jobs.to_csv(output, mode="a", header=False, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        logging.info("Appended %d job listings to %s", len(jobs), output)
    else:
        jobs.to_csv(output, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        logging.info("Saved %d job listings to %s", len(jobs), output)

    seen = load_seen_job_urls(seen_file)
    seen.update(jobs["job_url"].astype(str).tolist())
    save_seen_job_urls(seen, seen_file)

    run_market_analysis(
        output=output,
        analyzer_outputs=analyzer_outputs,
        profile=profile,
        filter_experience=filter_experience,
        exclude_senior=exclude_senior,
        experience_min=experience_min,
        experience_max=experience_max,
        keep_unknown_years=keep_unknown_years,
    )
    logging.info(
        "Key outputs in %s/: jobs.csv, jobs.html, market_summary.json",
        output_paths.output_dir,
    )


def main() -> None:
    default_search = CONFIG.get("search_terms") or [
        "data engineer",
        "analytics engineer",
        "etl engineer",
    ]
    default_locations = CONFIG.get("locations") or ["India", "Remote"]
    default_remote = CONFIG.get("remote_locations") or default_locations
    default_exp_min = int(CONFIG.get("experience_min", 2))
    default_exp_max = int(CONFIG.get("experience_max", 4))

    parser = argparse.ArgumentParser(
        description="JobFetcher CLI - Collect job listings and analyze the market"
    )
    parser.add_argument(
        "--search-terms",
        type=_parse_list,
        default=list(default_search),
        help="Comma-separated search terms",
    )
    parser.add_argument(
        "--locations",
        type=_parse_list,
        default=list(default_locations),
        help="Comma-separated locations to search",
    )
    parser.add_argument(
        "--remote-locations",
        type=_parse_list,
        default=list(default_remote),
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
    parser.add_argument("--links-html", help="Override HTML report path")
    parser.add_argument("--market-json", help="Override market JSON path")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append new jobs to the output file instead of overwriting",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Max parallel workers for fetching jobs across queries and sites",
    )
    parser.add_argument(
        "--include-seen",
        action="store_true",
        help="Include jobs already tracked in .seen_jobs.json",
    )
    parser.add_argument(
        "--reset-seen",
        action="store_true",
        help="Clear .seen_jobs.json before fetching",
    )
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Skip fetching and analyze the existing jobs CSV",
    )
    parser.add_argument(
        "--profile-skills",
        type=_parse_list,
        help="Candidate skills to match (defaults to config my_skills)",
    )
    parser.add_argument(
        "--experience-min",
        type=int,
        default=default_exp_min,
        help="Target minimum years of experience (default from config: 2)",
    )
    parser.add_argument(
        "--experience-max",
        type=int,
        default=default_exp_max,
        help="Maximum required years to keep (default from config: 4)",
    )
    parser.add_argument(
        "--profile-min-years",
        type=int,
        help="Alias for --experience-min",
    )
    parser.add_argument(
        "--profile-max-years",
        type=int,
        help="Alias for --experience-max",
    )
    parser.add_argument(
        "--hard-experience-filter",
        action="store_true",
        help="Hard-drop jobs outside the experience band (soft mode is default)",
    )
    parser.add_argument(
        "--no-experience-filter",
        action="store_true",
        help="Alias for soft mode: keep jobs outside the experience band (default)",
    )
    parser.add_argument(
        "--drop-senior",
        action="store_true",
        help="Hard-drop senior/staff/lead titles (soft mode keeps them by default)",
    )
    parser.add_argument(
        "--keep-senior",
        action="store_true",
        help="Alias for soft mode: keep senior/staff/lead titles (default)",
    )
    parser.add_argument(
        "--drop-unknown-years",
        action="store_true",
        help="Drop jobs with no detectable years requirement (only with hard experience filter)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    exp_min = args.profile_min_years if args.profile_min_years is not None else args.experience_min
    exp_max = args.profile_max_years if args.profile_max_years is not None else args.experience_max

    output_paths = OutputPaths.for_directory(args.output_dir)
    if args.output:
        output_paths = replace(output_paths, jobs_csv=Path(args.output))

    ensure_output_dir(output_paths.output_dir)
    logging.info("Writing outputs to %s/", output_paths.output_dir)
    logging.info("Experience band: %d–%d years", exp_min, exp_max)

    adzuna_creds = None
    if args.adzuna_id and args.adzuna_key:
        adzuna_creds = {"app_id": args.adzuna_id, "app_key": args.adzuna_key}

    analyzer_outputs = _build_analyzer_outputs(
        output_paths,
        links_html=args.links_html,
        market_json=args.market_json,
    )

    skills = args.profile_skills or CONFIG.get("my_skills") or ["python", "sql"]
    profile = ProfileFilter(
        skills=tuple(skill.lower() for skill in skills),
        min_years=exp_min,
        max_years=exp_max,
    )

    # Soft mode default: rank by score; optional hard drops via flags/config
    filter_experience = bool(CONFIG.get("filter_experience_band", False))
    if args.hard_experience_filter:
        filter_experience = True
    if args.no_experience_filter:
        filter_experience = False

    exclude_senior = bool(CONFIG.get("exclude_senior_titles", False))
    if args.drop_senior:
        exclude_senior = True
    if args.keep_senior:
        exclude_senior = False

    analysis_kwargs = {
        "profile": profile,
        "filter_experience": filter_experience,
        "exclude_senior": exclude_senior,
        "experience_min": exp_min,
        "experience_max": exp_max,
        "keep_unknown_years": not args.drop_unknown_years,
    }
    logging.info(
        "Mode: %s experience filter, %s senior titles",
        "HARD" if filter_experience else "SOFT",
        "drop" if exclude_senior else "keep (ranked)",
    )

    if args.analyze_only:
        run_market_analysis(
            output=str(output_paths.jobs_csv),
            analyzer_outputs=analyzer_outputs,
            **analysis_kwargs,
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
        **analysis_kwargs,
    )


if __name__ == "__main__":
    main()
