"""Enrich job listings and produce market-wide analysis summaries."""
from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import Dict, List, Optional

import pandas as pd

from .config import load_config
from .paths import DEFAULT_OUTPUT_DIR, OutputPaths, ensure_parent_dir

logger = logging.getLogger(__name__)

CONFIG = load_config()
KEY_SKILLS = CONFIG.get("key_skills", [])


@dataclass(frozen=True)
class ProfileFilter:
    skills: tuple[str, ...] = ("snowflake",)
    min_years: int = 2
    max_years: int = 6


@dataclass(frozen=True)
class AnalyzerOutputs:
    links_csv: str = "results/jobs_links.csv"
    links_html: str = "results/jobs.html"
    mid_csv: str = "results/mid_jobs.csv"
    mid_jsonl: str = "results/mid_jobs.jsonl"
    summary_json: str = "results/market_summary.json"
    summary_txt: str = "results/market_summary.txt"
    recurrence_file: str = "results/keywords_recurrence.json"
    profile_csv: str = "results/profile_matches.csv"
    profile_html: str = "results/profile_matches.html"

    @classmethod
    def from_output_paths(cls, paths: OutputPaths) -> AnalyzerOutputs:
        return cls(
            links_csv=str(paths.links_csv),
            links_html=str(paths.links_html),
            mid_csv=str(paths.mid_csv),
            mid_jsonl=str(paths.mid_jsonl),
            summary_json=str(paths.market_json),
            summary_txt=str(paths.market_txt),
            recurrence_file=str(paths.keywords_recurrence),
            profile_csv=str(paths.profile_csv),
            profile_html=str(paths.profile_html),
        )

    @classmethod
    def for_directory(cls, output_dir: str = DEFAULT_OUTPUT_DIR) -> AnalyzerOutputs:
        return cls.from_output_paths(OutputPaths.for_directory(output_dir))


# Constants for filtering and matching
SENIOR_RE = re.compile(r"\b(senior|sr\.?|lead|principal|manager|director|vp|chief)\b", re.I)
YEARS_RE = re.compile(
    r"(\d+)\s*(?:\+|(?:\s*(?:-|–|to)\s*(\d+)))?\s*years",
    re.I,
)


def estimate_years(text: str) -> Dict[str, Optional[int]]:
    """Estimate minimum and maximum years of experience from text."""
    if not isinstance(text, str):
        return {"min": None, "max": None}
    
    match = YEARS_RE.search(text)
    if not match:
        return {"min": None, "max": None}
    
    try:
        min_years = int(match.group(1))
    except (ValueError, TypeError):
        min_years = None
        
    max_years = None
    if match.group(2):
        try:
            max_years = int(match.group(2))
        except (ValueError, TypeError):
            max_years = None
            
    return {"min": min_years, "max": max_years}


def calculate_mid_level_score(title: str, description: str) -> float:
    """Score a job based on its likelihood of being mid-level."""
    score = 0.0
    title_lower = title.lower()
    desc_lower = description.lower()

    # Title boosts
    if "data engineer" in title_lower: score += 3.0
    if "analytics engineer" in title_lower: score += 3.0
    if "etl" in title_lower: score += 2.0
    if "software engineer" in title_lower: score += 1.0

    # Skill boosts (from config)
    skill_matches = 0
    for skill in KEY_SKILLS:
        if re.search(rf"\b{re.escape(skill)}\b", desc_lower, re.I):
            skill_matches += 1

    # Bonus for having multiple key skills
    if skill_matches >= 3: score += 2.0
    if skill_matches >= 7: score += 2.0

    # Senior/Lead penalties
    if SENIOR_RE.search(title): score -= 5.0
    if "principal" in title_lower: score -= 5.0
    if "director" in title_lower: score -= 5.0

    # Experience penalties in description
    if "10+ years" in desc_lower or "12+ years" in desc_lower: score -= 4.0

    return score

def is_mid_level_job(row: pd.Series) -> bool:
    """Determine if a job is mid-level using scoring and experience estimation."""
    title = str(row.get("title", ""))
    desc = str(row.get("description", ""))

    score = calculate_mid_level_score(title, desc)

    # Estimate years
    years = estimate_years(desc)
    min_y = years["min"]

    # Heuristic: high score OR (moderate score AND reasonable years)
    if score >= 4.0: return True
    if score >= 1.0 and (min_y is None or min_y <= 5): return True

    return False



def _text_mentions_skill(text: str, skill: str) -> bool:
    return bool(re.search(rf"\b{re.escape(skill)}\b", text, re.I))


def matches_profile(row: pd.Series, profile: ProfileFilter) -> bool:
    """Match jobs aligned with a candidate profile (skills + experience band)."""
    title = str(row.get("title", ""))
    description = str(row.get("description", ""))
    combined = f"{title} {description}".lower()

    if not any(_text_mentions_skill(combined, skill) for skill in profile.skills):
        return False

    if SENIOR_RE.search(title):
        return False

    description_lower = description.lower()
    if "10+ years" in description_lower or "12+ years" in description_lower:
        return False

    est_min = row.get("est_min_years")
    if pd.notna(est_min):
        if int(est_min) > profile.max_years:
            return False

    est_max = row.get("est_max_years")
    if pd.notna(est_max) and int(est_max) < profile.min_years:
        return False

    return True


def filter_profile_matches(df: pd.DataFrame, profile: ProfileFilter) -> pd.DataFrame:
    """Return jobs that match the candidate profile."""
    if df.empty:
        return df
    return df[df.apply(lambda row: matches_profile(row, profile), axis=1)].copy()


def enrich_jobs_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add market analysis fields to every job listing."""
    enriched = df.copy()
    enriched["title"] = enriched.get("title", pd.Series(dtype=str)).fillna("")
    enriched["description"] = enriched.get("description", pd.Series(dtype=str)).fillna("")
    enriched["mid_level_score"] = enriched.apply(
        lambda row: calculate_mid_level_score(row["title"], row["description"]),
        axis=1,
    )
    enriched["is_mid_level"] = enriched.apply(is_mid_level_job, axis=1)
    enriched["est_min_years"] = enriched["description"].apply(lambda text: estimate_years(text)["min"])
    enriched["est_max_years"] = enriched["description"].apply(lambda text: estimate_years(text)["max"])
    return enriched


def _save_mid_level_exports(mid_df: pd.DataFrame, outputs: AnalyzerOutputs) -> None:
    ensure_parent_dir(outputs.mid_csv)
    mid_df.to_csv(outputs.mid_csv, index=False, quoting=1)

    ensure_parent_dir(outputs.mid_jsonl)
    with open(outputs.mid_jsonl, "w", encoding="utf-8") as handle:
        for _, row in mid_df.iterrows():
            record = {
                "job_url": row.get("job_url"),
                "title": row.get("title"),
                "company": row.get("company"),
                "location": row.get("location"),
                "source_location": row.get("source_location"),
                "est_min_years": int(row["est_min_years"]) if pd.notnull(row["est_min_years"]) else None,
                "est_max_years": int(row["est_max_years"]) if pd.notnull(row["est_max_years"]) else None,
                "description": row.get("description"),
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _export_profile_matches(
    profile_df: pd.DataFrame,
    outputs: AnalyzerOutputs,
    profile: ProfileFilter,
) -> None:
    from .reports import write_jobs_html, write_jobs_links_csv

    if profile_df.empty:
        logger.warning(
            "No jobs matched your profile (skills=%s, experience ~%d-%d years).",
            ", ".join(profile.skills),
            profile.min_years,
            profile.max_years,
        )
        return

    write_jobs_links_csv(profile_df, outputs.profile_csv)
    write_jobs_html(profile_df, outputs.profile_html)
    logger.info(
        "Saved %d profile matches to %s and %s",
        len(profile_df),
        outputs.profile_csv,
        outputs.profile_html,
    )


def run_market_analysis(
    input_csv: str = "jobs.csv",
    outputs: Optional[AnalyzerOutputs] = None,
    export_mid_level: bool = True,
    profile: Optional[ProfileFilter] = None,
) -> pd.DataFrame:
    """Enrich all jobs, write link reports, and summarize the full market."""
    from .reports import write_jobs_html, write_jobs_links_csv

    outputs = outputs or AnalyzerOutputs()
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        logger.error("Input file %s not found.", input_csv)
        return pd.DataFrame()

    logger.info("Loaded %d rows from %s", len(df), input_csv)
    enriched = enrich_jobs_dataframe(df)
    mid_count = int(enriched["is_mid_level"].sum())
    logger.info(
        "Market view: %d total jobs (%d mid-level, %d other)",
        len(enriched),
        mid_count,
        len(enriched) - mid_count,
    )

    write_jobs_links_csv(enriched, outputs.links_csv)
    write_jobs_html(enriched, outputs.links_html)
    logger.info("Saved clickable job list to %s and %s", outputs.links_csv, outputs.links_html)

    summarize_market(enriched, outputs=outputs)

    if export_mid_level:
        mid_df = enriched[enriched["is_mid_level"]].copy()
        _save_mid_level_exports(mid_df, outputs)
        logger.info("Saved %d mid-level jobs to %s", len(mid_df), outputs.mid_csv)

    if profile is not None:
        profile_df = filter_profile_matches(enriched, profile)
        _export_profile_matches(profile_df, outputs, profile)

    return enriched


def main(
    input_csv: str = "jobs.csv",
    outputs: Optional[AnalyzerOutputs] = None,
) -> str:
    """Backward-compatible entry point for market analysis."""
    outputs = outputs or AnalyzerOutputs()
    enriched = run_market_analysis(input_csv=input_csv, outputs=outputs)
    return outputs.mid_csv if not enriched.empty else input_csv


def summarize_market(
    df: pd.DataFrame,
    outputs: Optional[AnalyzerOutputs] = None,
    top_n: int = 30,
) -> None:
    """Analyze all job listings and produce market summaries."""
    outputs = outputs or AnalyzerOutputs()
    out_json = outputs.summary_json
    out_txt = outputs.summary_txt
    recurrence_file = outputs.recurrence_file

    if df.empty:
        logger.warning("No jobs available for market summarization")
        return

    # Combine title and description for keyword analysis
    texts = (df.get("title", pd.Series()).fillna("") + " " + df.get("description", pd.Series()).fillna("")).astype(str)

    # Count skill mentions
    current_counts = Counter()
    for text in texts:
        text_lower = text.lower()
        for skill in KEY_SKILLS:
            if re.search(rf"\b{re.escape(skill)}\b", text_lower, re.I):
                current_counts[skill] += 1

    # Update persistent keyword recurrence across runs
    persistent_counts = {}
    if os.path.exists(recurrence_file):
        try:
            with open(recurrence_file, "r", encoding="utf-8") as f:
                persistent_counts = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {recurrence_file}: {e}")

    for skill, count in current_counts.items():
        persistent_counts[skill] = persistent_counts.get(skill, 0) + count

    try:
        ensure_parent_dir(recurrence_file)
        with open(recurrence_file, "w", encoding="utf-8") as f:
            json.dump(persistent_counts, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to update {recurrence_file}: {e}")

    # Education degree mentions
    degree_patterns = {
        "bachelor": r"\bbachelor\b|\bbs\b|\bb\.sc\b",
        "master": r"\bmaster\b|\bms\b|\bm\.sc\b",
        "phd": r"\bphd\b|\bdoctorate\b"
    }
    degree_counts = Counter()
    for text in texts:
        text_lower = text.lower()
        for deg, pattern in degree_patterns.items():
            if re.search(pattern, text_lower, re.I):
                degree_counts[deg] += 1

    # Experience statistics
    min_years = df.get("est_min_years").dropna()
    max_years = df.get("est_max_years").dropna()
    avg_min = float(min_years.mean()) if not min_years.empty else None
    avg_max = float(max_years.mean()) if not max_years.empty else None

    mid_level_count = int(df["is_mid_level"].sum()) if "is_mid_level" in df.columns else 0
    summary = {
        "total_jobs": len(df),
        "mid_level_jobs": mid_level_count,
        "top_skills": current_counts.most_common(top_n),
        "persistent_total_recurrence": sorted(persistent_counts.items(), key=lambda x: x[1], reverse=True)[:top_n],
        "degree_counts": degree_counts.most_common(),
        "avg_est_min_years": avg_min,
        "avg_est_max_years": avg_max,
        "jobs_by_site": df.get("site", pd.Series()).fillna("unknown").value_counts().head(12).to_dict(),
        "jobs_by_location": df.get("source_location", pd.Series()).fillna("unknown").value_counts().head(12).to_dict(),
        "top_titles": df.get("title", pd.Series()).value_counts().head(12).to_dict(),
        "top_companies": df.get("company", pd.Series()).value_counts().head(12).to_dict(),
        "sample_jobs": [
            {"title": r.title, "company": r.company, "location": r.location, "url": r.job_url}
            for r in df.head(6).itertuples()
        ],
    }

    # Write JSON summary
    try:
        ensure_parent_dir(out_json)
        with open(out_json, "w", encoding="utf-8") as jfh:
            json.dump(summary, jfh, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to write JSON summary: {e}")

    # Write Human-readable text summary
    try:
        ensure_parent_dir(out_txt)
        with open(out_txt, "w", encoding="utf-8") as tfh:
            tfh.write("Job market summary\n")
            tfh.write("=" * 40 + "\n")
            tfh.write(f"Total jobs analyzed: {len(df)}\n")
            tfh.write(f"Mid-level jobs: {mid_level_count}\n\n")
            tfh.write("Jobs by site:\n")
            for site, count in summary["jobs_by_site"].items():
                tfh.write(f"- {site}: {count}\n")
            tfh.write("\nJobs by search location:\n")
            for location, count in summary["jobs_by_location"].items():
                tfh.write(f"- {location}: {count}\n")
            tfh.write("\nTop skills in this run:\n")
            for skill, cnt in summary["top_skills"]:
                tfh.write(f"- {skill}: {cnt}\n")
            tfh.write("\nPersistent Keyword Recurrence (All Runs):\n")
            for skill, cnt in summary["persistent_total_recurrence"]:
                tfh.write(f"- {skill}: {cnt}\n")
            tfh.write("\nEducation mentions:\n")
            for deg, cnt in degree_counts.most_common():
                tfh.write(f"- {deg}: {cnt}\n")
            avg_min_str = f"{avg_min:.1f}y" if avg_min is not None else "N/A"
            avg_max_str = f"{avg_max:.1f}y" if avg_max is not None else "N/A"
            tfh.write(f"\nEstimated experience: avg min {avg_min_str}, avg max {avg_max_str}\n\n")
            tfh.write("Top titles:\n")
            for t, c in summary["top_titles"].items():
                tfh.write(f"- {t}: {c}\n")
            tfh.write("\nSample jobs:\n")
            for s in summary["sample_jobs"]:
                tfh.write(f"- {s['title']} | {s['company']} | {s['location']} | {s['url']}\n")
    except Exception as e:
        logger.error(f"Failed to write text summary: {e}")


def summarize_requirements(
    input_csv: str = "jobs.csv",
    outputs: Optional[AnalyzerOutputs] = None,
    top_n: int = 30,
) -> None:
    """Backward-compatible alias for market summarization."""
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        logger.warning("Could not read %s for requirement summarization", input_csv)
        return
    summarize_market(enrich_jobs_dataframe(df), outputs=outputs, top_n=top_n)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for analysis outputs")
    parser.add_argument("--input", help="Input jobs CSV (defaults to <output-dir>/jobs.csv)")
    parser.add_argument("--links-csv", help="Override links CSV path")
    parser.add_argument("--links-html", help="Override HTML report path")
    parser.add_argument("--mid-jobs-output", help="Override mid-level CSV path")
    parser.add_argument("--mid-jobs-jsonl", help="Override mid-level JSONL path")
    parser.add_argument("--market-json", help="Override market JSON path")
    parser.add_argument("--market-txt", help="Override market text path")
    parser.add_argument("--keywords-recurrence", help="Override keyword recurrence path")
    args = parser.parse_args()

    output_paths = OutputPaths.for_directory(args.output_dir)
    analyzer_outputs = AnalyzerOutputs.from_output_paths(output_paths)
    overrides = {
        "links_csv": args.links_csv,
        "links_html": args.links_html,
        "mid_csv": args.mid_jobs_output,
        "mid_jsonl": args.mid_jobs_jsonl,
        "summary_json": args.market_json,
        "summary_txt": args.market_txt,
        "recurrence_file": args.keywords_recurrence,
    }
    analyzer_outputs = replace(
        analyzer_outputs,
        **{key: value for key, value in overrides.items() if value is not None},
    )

    input_csv = args.input or str(output_paths.jobs_csv)
    run_market_analysis(input_csv=input_csv, outputs=analyzer_outputs)
