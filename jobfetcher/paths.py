"""Filesystem helpers for output paths."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]

DEFAULT_OUTPUT_DIR = "results"


@dataclass(frozen=True)
class OutputPaths:
    """Deliverable paths (3 files) plus hidden internal state for dedup."""

    output_dir: Path
    jobs_csv: Path
    links_html: Path
    market_json: Path
    seen_jobs: Path  # hidden state file, not a user deliverable

    @classmethod
    def for_directory(cls, output_dir: PathLike = DEFAULT_OUTPUT_DIR) -> OutputPaths:
        base = Path(output_dir)
        return cls(
            output_dir=base,
            jobs_csv=base / "jobs.csv",
            links_html=base / "jobs.html",
            market_json=base / "market_summary.json",
            seen_jobs=base / ".seen_jobs.json",
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
