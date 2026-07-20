"""Enrich job listings and produce market-wide analysis summaries."""
from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence

import pandas as pd

from .config import load_config
from .paths import DEFAULT_OUTPUT_DIR, OutputPaths, ensure_parent_dir
from .title_filter import filter_data_engineering_jobs, filter_senior_titles, is_senior_title
from .years import estimate_years, overlaps_experience_band

logger = logging.getLogger(__name__)

CONFIG = load_config()
KEY_SKILLS = CONFIG.get("key_skills", [])
MUST_SKILLS = [s.lower() for s in CONFIG.get("must_skills", ["python", "sql"])]
NICE_SKILLS = [s.lower() for s in CONFIG.get("nice_skills", [])]
MY_SKILLS = [s.lower() for s in CONFIG.get("my_skills", MUST_SKILLS + NICE_SKILLS)]
EXPERIENCE_MIN = int(CONFIG.get("experience_min", 2))
EXPERIENCE_MAX = int(CONFIG.get("experience_max", 4))
KEEP_UNKNOWN_YEARS = bool(CONFIG.get("keep_unknown_years", True))
# Soft defaults: keep all DE jobs; rank by score; use band only for flags/HTML
FILTER_EXPERIENCE_BAND = bool(CONFIG.get("filter_experience_band", False))
EXCLUDE_SENIOR_TITLES = bool(CONFIG.get("exclude_senior_titles", False))


@dataclass(frozen=True)
class ProfileFilter:
    skills: tuple[str, ...] = tuple(MY_SKILLS) if MY_SKILLS else ("python", "sql")
    min_years: int = EXPERIENCE_MIN
    max_years: int = EXPERIENCE_MAX


@dataclass(frozen=True)
class AnalyzerOutputs:
    """Paths for the two analyzer-written deliverables (jobs.csv is updated by the CLI)."""

    links_html: str = "results/jobs.html"
    summary_json: str = "results/market_summary.json"

    @classmethod
    def from_output_paths(cls, paths: OutputPaths) -> AnalyzerOutputs:
        return cls(
            links_html=str(paths.links_html),
            summary_json=str(paths.market_json),
        )

    @classmethod
    def for_directory(cls, output_dir: str = DEFAULT_OUTPUT_DIR) -> AnalyzerOutputs:
        return cls.from_output_paths(OutputPaths.for_directory(output_dir))


SENIOR_RE = re.compile(
    r"\b(senior|sr\.?|lead|principal|manager|director|vp|chief|staff)\b",
    re.I,
)


def calculate_mid_level_score(title: str, description: str) -> float:
    """Score a job based on its likelihood of being mid-level."""
    score = 0.0
    title_lower = title.lower()
    desc_lower = description.lower()

    if "data engineer" in title_lower:
        score += 3.0
    if "analytics engineer" in title_lower:
        score += 3.0
    if "etl" in title_lower:
        score += 2.0
    if "software engineer" in title_lower:
        score += 1.0

    skill_matches = 0
    for skill in KEY_SKILLS:
        if re.search(rf"\b{re.escape(skill)}\b", desc_lower, re.I):
            skill_matches += 1

    if skill_matches >= 3:
        score += 2.0
    if skill_matches >= 7:
        score += 2.0

    if SENIOR_RE.search(title):
        score -= 5.0
    if "principal" in title_lower:
        score -= 5.0
    if "director" in title_lower:
        score -= 5.0

    years = estimate_years(description)
    min_y = years["min"]
    if min_y is not None and min_y >= 8:
        score -= 4.0
    if min_y is not None and 2 <= min_y <= 4:
        score += 2.0

    return score


def is_mid_level_job(row: pd.Series) -> bool:
    """Determine if a job is mid-level using scoring and experience estimation."""
    title = str(row.get("title", ""))
    desc = str(row.get("description", ""))

    score = calculate_mid_level_score(title, desc)
    years = estimate_years(desc)
    min_y = years["min"]

    if is_senior_title(title):
        return False
    if min_y is not None and min_y > 5:
        return False
    if score >= 4.0:
        return True
    if score >= 1.0 and (min_y is None or min_y <= 5):
        return True
    return False


def _text_mentions_skill(text: str, skill: str) -> bool:
    return bool(re.search(rf"\b{re.escape(skill)}\b", text, re.I))


def matched_skills(text: str, skills: Sequence[str]) -> list[str]:
    return [skill for skill in skills if _text_mentions_skill(text, skill)]


def calculate_match_score(
    row: pd.Series,
    must_skills: Optional[Sequence[str]] = None,
    nice_skills: Optional[Sequence[str]] = None,
    band_min: int = EXPERIENCE_MIN,
    band_max: int = EXPERIENCE_MAX,
) -> float:
    """Personal fit score for a 2–4 year data engineer profile."""
    must_skills = list(must_skills or MUST_SKILLS)
    nice_skills = list(nice_skills or NICE_SKILLS)

    title = str(row.get("title", "") or "")
    description = str(row.get("description", "") or "")
    combined = f"{title}\n{description}"

    score = 0.0
    must_hits = matched_skills(combined, must_skills)
    nice_hits = matched_skills(combined, nice_skills)

    score += 5.0 * len(must_hits)
    score -= 3.0 * (len(must_skills) - len(must_hits))
    score += 2.0 * len(nice_hits)

    if "data engineer" in title.lower():
        score += 3.0
    if "analytics engineer" in title.lower():
        score += 2.0

    if is_senior_title(title) or SENIOR_RE.search(title):
        score -= 8.0

    est_min = row.get("est_min_years")
    est_max = row.get("est_max_years")
    min_y = int(est_min) if pd.notna(est_min) else None
    max_y = int(est_max) if pd.notna(est_max) else None

    if min_y is not None and band_min <= min_y <= band_max:
        score += 6.0
    elif min_y is not None and min_y > band_max:
        score -= 6.0
    elif min_y is None:
        score += 1.0  # unknown years: mild benefit so they stay visible

    if max_y is not None and max_y < band_min:
        score -= 3.0

    if bool(row.get("is_fortune_500")):
        score += 1.0
    if bool(row.get("is_mid_level")):
        score += 2.0

    return round(score, 2)


def matches_profile(row: pd.Series, profile: ProfileFilter) -> bool:
    """Match jobs aligned with a candidate profile (skills + experience band)."""
    title = str(row.get("title", ""))
    description = str(row.get("description", ""))
    combined = f"{title} {description}".lower()

    if not any(_text_mentions_skill(combined, skill) for skill in profile.skills):
        return False

    if is_senior_title(title) or SENIOR_RE.search(title):
        return False

    est_min = row.get("est_min_years")
    est_max = row.get("est_max_years")
    min_y = int(est_min) if pd.notna(est_min) else None
    max_y = int(est_max) if pd.notna(est_max) else None
    return overlaps_experience_band(
        min_y,
        max_y,
        band_min=profile.min_years,
        band_max=profile.max_years,
        keep_unknown=KEEP_UNKNOWN_YEARS,
    )


def filter_profile_matches(df: pd.DataFrame, profile: ProfileFilter) -> pd.DataFrame:
    """Return jobs that match the candidate profile."""
    if df.empty:
        return df
    return df[df.apply(lambda row: matches_profile(row, profile), axis=1)].copy()


def filter_experience_band(
    df: pd.DataFrame,
    band_min: int = EXPERIENCE_MIN,
    band_max: int = EXPERIENCE_MAX,
    keep_unknown: bool = KEEP_UNKNOWN_YEARS,
) -> pd.DataFrame:
    """Keep jobs whose estimated experience overlaps the candidate band."""
    if df.empty:
        return df

    def _ok(row: pd.Series) -> bool:
        est_min = row.get("est_min_years")
        est_max = row.get("est_max_years")
        min_y = int(est_min) if pd.notna(est_min) else None
        max_y = int(est_max) if pd.notna(est_max) else None
        return overlaps_experience_band(
            min_y,
            max_y,
            band_min=band_min,
            band_max=band_max,
            keep_unknown=keep_unknown,
        )

    return df[df.apply(_ok, axis=1)].copy()


def enrich_jobs_dataframe(
    df: pd.DataFrame,
    profile: Optional[ProfileFilter] = None,
) -> pd.DataFrame:
    """Add market analysis fields to every job listing."""
    enriched = df.copy()
    enriched["title"] = enriched.get("title", pd.Series(dtype=str)).fillna("")
    enriched["description"] = enriched.get("description", pd.Series(dtype=str)).fillna("")

    years = enriched["description"].apply(estimate_years)
    enriched["est_min_years"] = years.apply(lambda item: item["min"])
    enriched["est_max_years"] = years.apply(lambda item: item["max"])

    enriched["mid_level_score"] = enriched.apply(
        lambda row: calculate_mid_level_score(row["title"], row["description"]),
        axis=1,
    )
    enriched["is_mid_level"] = enriched.apply(is_mid_level_job, axis=1)

    active_profile = profile or ProfileFilter()
    enriched["matched_skills"] = enriched.apply(
        lambda row: ", ".join(
            matched_skills(
                f"{row['title']} {row['description']}",
                MY_SKILLS or list(active_profile.skills),
            )
        ),
        axis=1,
    )
    enriched["match_score"] = enriched.apply(calculate_match_score, axis=1)
    enriched["is_profile_match"] = enriched.apply(
        lambda row: matches_profile(row, active_profile),
        axis=1,
    )
    # Soft approach: flag band fit without dropping rows
    band_min = active_profile.min_years
    band_max = active_profile.max_years

    def _in_band(row: pd.Series) -> bool:
        est_min = row.get("est_min_years")
        est_max = row.get("est_max_years")
        min_y = int(est_min) if pd.notna(est_min) else None
        max_y = int(est_max) if pd.notna(est_max) else None
        return overlaps_experience_band(
            min_y,
            max_y,
            band_min=band_min,
            band_max=band_max,
            keep_unknown=KEEP_UNKNOWN_YEARS,
        )

    enriched["in_experience_band"] = enriched.apply(_in_band, axis=1)
    return enriched


def run_market_analysis(
    input_csv: str = "jobs.csv",
    outputs: Optional[AnalyzerOutputs] = None,
    profile: Optional[ProfileFilter] = None,
    filter_experience: Optional[bool] = None,
    exclude_senior: Optional[bool] = None,
    experience_min: Optional[int] = None,
    experience_max: Optional[int] = None,
    keep_unknown_years: Optional[bool] = None,
) -> pd.DataFrame:
    """Enrich all jobs, write the HTML report, and summarize the market."""
    from .reports import write_jobs_html

    outputs = outputs or AnalyzerOutputs()
    do_exp = FILTER_EXPERIENCE_BAND if filter_experience is None else filter_experience
    do_senior = EXCLUDE_SENIOR_TITLES if exclude_senior is None else exclude_senior
    band_min = EXPERIENCE_MIN if experience_min is None else experience_min
    band_max = EXPERIENCE_MAX if experience_max is None else experience_max
    keep_unknown = KEEP_UNKNOWN_YEARS if keep_unknown_years is None else keep_unknown_years

    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        logger.error("Input file %s not found.", input_csv)
        return pd.DataFrame()

    logger.info("Loaded %d rows from %s", len(df), input_csv)
    before_title = len(df)
    df = filter_data_engineering_jobs(df)
    dropped = before_title - len(df)
    if dropped:
        logger.info(
            "Dropped %d non data-engineering titles before analysis (kept %d)",
            dropped,
            len(df),
        )
    if df.empty:
        logger.error("No data-engineering jobs left after title filtering.")
        return pd.DataFrame()

    if do_senior:
        before = len(df)
        df = filter_senior_titles(df)
        dropped_senior = before - len(df)
        if dropped_senior:
            logger.info(
                "Dropped %d senior/staff/lead titles (kept %d)",
                dropped_senior,
                len(df),
            )
        if df.empty:
            logger.error("No jobs left after senior-title filtering.")
            return pd.DataFrame()
    else:
        logger.info(
            "Soft mode: keeping senior/staff titles (ranked lower by match_score)"
        )

    active_profile = profile or ProfileFilter(min_years=band_min, max_years=band_max)
    enriched = enrich_jobs_dataframe(df, profile=active_profile)

    if do_exp:
        before = len(enriched)
        enriched = filter_experience_band(
            enriched,
            band_min=band_min,
            band_max=band_max,
            keep_unknown=keep_unknown,
        )
        dropped_exp = before - len(enriched)
        if dropped_exp:
            logger.info(
                "Dropped %d jobs outside %d–%d year band (kept %d; unknown_years=%s)",
                dropped_exp,
                band_min,
                band_max,
                len(enriched),
                keep_unknown,
            )
        if enriched.empty:
            logger.error("No jobs left after experience-band filtering.")
            return pd.DataFrame()
    else:
        in_band = (
            int(enriched["in_experience_band"].sum())
            if "in_experience_band" in enriched.columns
            else 0
        )
        logger.info(
            "Soft mode: no hard YoE drop — %d/%d jobs flagged in %d–%d year band "
            "(use HTML filters / match_score to focus)",
            in_band,
            len(enriched),
            band_min,
            band_max,
        )

    # Best matches first (score already penalizes senior + high YoE)
    sort_cols = [
        c
        for c in ("match_score", "in_experience_band", "is_mid_level", "is_fortune_500")
        if c in enriched.columns
    ]
    if sort_cols:
        enriched = enriched.sort_values(
            by=sort_cols,
            ascending=[False] * len(sort_cols),
        ).reset_index(drop=True)

    mid_count = int(enriched["is_mid_level"].sum()) if "is_mid_level" in enriched.columns else 0
    profile_count = (
        int(enriched["is_profile_match"].sum())
        if "is_profile_match" in enriched.columns
        else None
    )
    logger.info(
        "Market view: %d total jobs (%d mid-level, %d other)",
        len(enriched),
        mid_count,
        len(enriched) - mid_count,
    )
    if profile_count is not None:
        logger.info("Profile matches (ideal 2–4y fit): %d", profile_count)
    if "match_score" in enriched.columns and not enriched.empty:
        logger.info(
            "Match score range: min=%.1f median=%.1f max=%.1f",
            float(enriched["match_score"].min()),
            float(enriched["match_score"].median()),
            float(enriched["match_score"].max()),
        )

    write_jobs_html(
        enriched,
        outputs.links_html,
        default_min_years=band_min,
        default_max_years=band_max,
        default_mid_level=True,
        profile_skills=list(active_profile.skills),
    )
    logger.info("Saved clickable job list to %s", outputs.links_html)

    summarize_market(enriched, outputs=outputs)
    return enriched


def main(
    input_csv: str = "jobs.csv",
    outputs: Optional[AnalyzerOutputs] = None,
) -> str:
    """Backward-compatible entry point for market analysis."""
    outputs = outputs or AnalyzerOutputs()
    enriched = run_market_analysis(input_csv=input_csv, outputs=outputs)
    return input_csv if not enriched.empty else input_csv


def _load_persistent_recurrence(summary_path: str) -> dict:
    """Load keyword recurrence from a previous market_summary.json if present."""
    if not os.path.exists(summary_path):
        return {}
    try:
        with open(summary_path, "r", encoding="utf-8") as handle:
            previous = json.load(handle)
        recurrence = previous.get("persistent_total_recurrence", [])
        if isinstance(recurrence, dict):
            return {str(k): int(v) for k, v in recurrence.items()}
        if isinstance(recurrence, list):
            result = {}
            for item in recurrence:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    result[str(item[0])] = int(item[1])
            return result
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Failed to load recurrence from %s: %s", summary_path, exc)
    return {}


def summarize_market(
    df: pd.DataFrame,
    outputs: Optional[AnalyzerOutputs] = None,
    top_n: int = 30,
) -> None:
    """Analyze all job listings and write market_summary.json."""
    outputs = outputs or AnalyzerOutputs()
    out_json = outputs.summary_json

    if df.empty:
        logger.warning("No jobs available for market summarization")
        return

    texts = (
        df.get("title", pd.Series()).fillna("")
        + " "
        + df.get("description", pd.Series()).fillna("")
    ).astype(str)

    current_counts: Counter = Counter()
    for text in texts:
        text_lower = text.lower()
        for skill in KEY_SKILLS:
            if re.search(rf"\b{re.escape(skill)}\b", text_lower, re.I):
                current_counts[skill] += 1

    persistent_counts = _load_persistent_recurrence(out_json)
    for skill, count in current_counts.items():
        persistent_counts[skill] = persistent_counts.get(skill, 0) + count

    degree_patterns = {
        "bachelor": r"\bbachelor\b|\bbs\b|\bb\.sc\b",
        "master": r"\bmaster\b|\bms\b|\bm\.sc\b",
        "phd": r"\bphd\b|\bdoctorate\b",
    }
    degree_counts: Counter = Counter()
    for text in texts:
        text_lower = text.lower()
        for deg, pattern in degree_patterns.items():
            if re.search(pattern, text_lower, re.I):
                degree_counts[deg] += 1

    min_years = df.get("est_min_years").dropna() if "est_min_years" in df.columns else pd.Series(dtype=float)
    max_years = df.get("est_max_years").dropna() if "est_max_years" in df.columns else pd.Series(dtype=float)
    avg_min = float(min_years.mean()) if not min_years.empty else None
    avg_max = float(max_years.mean()) if not max_years.empty else None

    mid_level_count = int(df["is_mid_level"].sum()) if "is_mid_level" in df.columns else 0
    profile_match_count = (
        int(df["is_profile_match"].sum()) if "is_profile_match" in df.columns else None
    )

    summary = {
        "total_jobs": len(df),
        "mid_level_jobs": mid_level_count,
        "experience_band": {"min": EXPERIENCE_MIN, "max": EXPERIENCE_MAX},
        "top_skills": current_counts.most_common(top_n),
        "persistent_total_recurrence": sorted(
            persistent_counts.items(), key=lambda x: x[1], reverse=True
        )[:top_n],
        "degree_counts": degree_counts.most_common(),
        "avg_est_min_years": avg_min,
        "avg_est_max_years": avg_max,
        "jobs_by_site": df.get("site", pd.Series()).fillna("unknown").value_counts().head(12).to_dict(),
        "jobs_by_location": df.get("source_location", pd.Series())
        .fillna("unknown")
        .value_counts()
        .head(12)
        .to_dict(),
        "top_titles": df.get("title", pd.Series()).value_counts().head(12).to_dict(),
        "top_companies": df.get("company", pd.Series()).value_counts().head(12).to_dict(),
        "top_match_jobs": [
            {
                "title": r.title,
                "company": r.company,
                "location": r.location,
                "match_score": getattr(r, "match_score", None),
                "url": r.job_url,
            }
            for r in df.head(6).itertuples()
        ],
        "sample_jobs": [
            {"title": r.title, "company": r.company, "location": r.location, "url": r.job_url}
            for r in df.head(6).itertuples()
        ],
    }
    if profile_match_count is not None:
        summary["profile_match_jobs"] = profile_match_count

    try:
        ensure_parent_dir(out_json)
        with open(out_json, "w", encoding="utf-8") as jfh:
            json.dump(summary, jfh, ensure_ascii=False, indent=2)
        logger.info("Market summary written to %s", out_json)
    except OSError as e:
        logger.error("Failed to write JSON summary: %s", e)


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


# Re-export for older imports/tests
__all__ = [
    "ProfileFilter",
    "AnalyzerOutputs",
    "estimate_years",
    "calculate_mid_level_score",
    "calculate_match_score",
    "is_mid_level_job",
    "matches_profile",
    "filter_profile_matches",
    "filter_experience_band",
    "enrich_jobs_dataframe",
    "run_market_analysis",
    "summarize_market",
    "summarize_requirements",
    "main",
]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Directory for analysis outputs")
    parser.add_argument("--input", help="Input jobs CSV (defaults to <output-dir>/jobs.csv)")
    parser.add_argument("--links-html", help="Override HTML report path")
    parser.add_argument("--market-json", help="Override market JSON path")
    args = parser.parse_args()

    output_paths = OutputPaths.for_directory(args.output_dir)
    analyzer_outputs = AnalyzerOutputs.from_output_paths(output_paths)
    overrides = {
        "links_html": args.links_html,
        "summary_json": args.market_json,
    }
    analyzer_outputs = replace(
        analyzer_outputs,
        **{key: value for key, value in overrides.items() if value is not None},
    )

    input_csv = args.input or str(output_paths.jobs_csv)
    run_market_analysis(input_csv=input_csv, outputs=analyzer_outputs)
