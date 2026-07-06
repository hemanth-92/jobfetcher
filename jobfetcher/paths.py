"""Filesystem helpers for output paths."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

DEFAULT_OUTPUT_DIR = "results"


@dataclass(frozen=True)
class OutputPaths:
    output_dir: Path
    jobs_csv: Path
    descriptions_txt: Path
    links_csv: Path
    links_html: Path
    mid_csv: Path
    mid_jsonl: Path
    market_json: Path
    market_txt: Path
    keywords_recurrence: Path
    seen_jobs: Path
    trend_log: Path
    profile_csv: Path
    profile_html: Path

    @classmethod
    def for_directory(cls, output_dir: PathLike = DEFAULT_OUTPUT_DIR) -> OutputPaths:
        base = Path(output_dir)
        return cls(
            output_dir=base,
            jobs_csv=base / "jobs.csv",
            descriptions_txt=base / "job_descriptions.txt",
            links_csv=base / "jobs_links.csv",
            links_html=base / "jobs.html",
            mid_csv=base / "mid_jobs.csv",
            mid_jsonl=base / "mid_jobs.jsonl",
            market_json=base / "market_summary.json",
            market_txt=base / "market_summary.txt",
            keywords_recurrence=base / "keywords_recurrence.json",
            seen_jobs=base / "seen_jobs.json",
            trend_log=base / "job_trends.log",
            profile_csv=base / "profile_matches.csv",
            profile_html=base / "profile_matches.html",
        )


def ensure_output_dir(output_dir: PathLike = DEFAULT_OUTPUT_DIR) -> Path:
    """Create the output directory when needed."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_parent_dir(path: PathLike) -> Path:
    """Create parent directories for a file path when needed."""
    file_path = Path(path)
    parent = file_path.parent
    if parent != Path("."):
        parent.mkdir(parents=True, exist_ok=True)
    return file_path