"""Extract mid-level data engineering jobs and produce structured logs and summaries."""
from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Configuration
def load_config(path: str = "config.json") -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load config {path}: {e}")
        return {"key_skills": []}

CONFIG = load_config()
KEY_SKILLS = CONFIG.get("key_skills", [])

# Constants for filtering and matching
SENIOR_RE = re.compile(r"\b(senior|sr\.?|lead|principal|manager|director|vp|chief)\b", re.I)
YEARS_RE = re.compile(r"(\d+)(?:\s*(?:\+|\-|to|–)\s*(\d+))?\s+years", re.I)


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



def main(input_csv: str = "jobs.csv") -> None:
    """Extract mid-level jobs from an input CSV and save them."""
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        logger.error(f"Input file {input_csv} not found.")
        return

    logger.info("Loaded %d rows from %s", len(df), input_csv)
    df["title"] = df.get("title", pd.Series(dtype=str)).fillna("")
    df["description"] = df.get("description", pd.Series(dtype=str)).fillna("")

    # Filter for mid-level roles using the scoring system
    mid_df = df[df.apply(is_mid_level_job, axis=1)].copy()

    # Estimate years for the remaining jobs
    desc_series = mid_df["description"]
    mid_df["est_min_years"] = desc_series.apply(lambda s: estimate_years(s)["min"])
    mid_df["est_max_years"] = desc_series.apply(lambda s: estimate_years(s)["max"])

    logger.info("Identified %d mid-level jobs after scoring and filtering", len(mid_df))

    # Save outputs
    mid_df.to_csv("mid_jobs.csv", index=False, quoting=1)

    with open("mid_jobs.jsonl", "w", encoding="utf-8") as fh:
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
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def summarize_requirements(
    input_csv: str = "mid_jobs.csv",
    out_json: str = "requirements_summary.json",
    out_txt: str = "requirements_summary.txt",
    recurrence_file: str = "keywords_recurrence.json",
    top_n: int = 30,
) -> None:
    """Analyze job requirements and produce summaries."""
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        logger.warning(f"Could not read {input_csv} for requirement summarization")
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

    # Prepare summary data
    summary = {
        "total_mid_jobs": len(df),
        "top_skills": current_counts.most_common(top_n),
        "persistent_total_recurrence": sorted(persistent_counts.items(), key=lambda x: x[1], reverse=True)[:top_n],
        "degree_counts": degree_counts.most_common(),
        "avg_est_min_years": avg_min,
        "avg_est_max_years": avg_max,
        "top_titles": df.get("title", pd.Series()).value_counts().head(12).to_dict(),
        "top_companies": df.get("company", pd.Series()).value_counts().head(12).to_dict(),
        "sample_jobs": [
            {"title": r.title, "company": r.company, "location": r.location, "url": r.job_url}
            for r in df.head(6).itertuples()
        ],
    }

    # Write JSON summary
    try:
        with open(out_json, "w", encoding="utf-8") as jfh:
            json.dump(summary, jfh, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to write JSON summary: {e}")

    # Write Human-readable text summary
    try:
        with open(out_txt, "w", encoding="utf-8") as tfh:
            tfh.write("Requirements summary\n")
            tfh.write("=" * 40 + "\n")
            tfh.write(f"Total mid-level jobs analyzed: {len(df)}\n\n")
            tfh.write("Top skills in this run:\n")
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="jobs.csv")
    args = parser.parse_args()
    main(input_csv=args.input)
    if os.path.exists("mid_jobs.csv"):
        summarize_requirements(input_csv="mid_jobs.csv")
