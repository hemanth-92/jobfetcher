"""Keep only data-engineering-style job titles."""
from __future__ import annotations

import re
from typing import Iterable, Optional

import pandas as pd

from .config import load_config

# Titles that clearly signal a data engineering role
DEFAULT_INCLUDE_PATTERNS: tuple[str, ...] = (
    r"data\s*engineer",
    r"analytics\s*engineer",
    r"etl\s*(engineer|developer)",
    r"data\s*pipeline",
    r"pipeline\s*engineer",
    r"big\s*data\s*engineer",
    r"data\s*platform\s*engineer",
    r"data\s*infra(structure)?\s*engineer",
    r"data\s*warehouse\s*engineer",
    r"warehouse\s*engineer",
    r"lakehouse\s*engineer",
    r"snowflake\s*engineer",
    r"dbt\s*engineer",
    r"dataops",
    r"data\s*ops",
    r"data\s*integration\s*engineer",
    r"spark\s*engineer",
    r"cloud\s*data\s*engineer",
    r"azure\s*data\s*engineer",
    r"aws\s*data\s*engineer",
    r"gcp\s*data\s*engineer",
    r"business\s*intelligence\s*engineer",
    r"\bbi\s*engineer\b",
    r"database\s*engineer",
    r"data\s*architect",
    r"data\s*modeller",
    r"data\s*modeler",
)

# Drop even when the title is loosely data-related
DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    r"front[\s\-]*end",
    r"full[\s\-]*stack",
    r"fullstack",
    r"\bbackend\b",
    r"back[\s\-]*end",
    r"sales\s*engineer",
    r"data\s*analyst",
    r"data\s*scientist",
    r"data\s*science",
    r"machine\s*learning",
    r"\bml\s*engineer\b",
    r"\bai\s*engineer\b",
    r"product\s*engineer",
    r"\bmobile\b",
    r"\bios\b",
    r"\bandroid\b",
    r"\bqa\b",
    r"test\s*engineer",
    r"support\s*engineer",
    r"service\s*desk",
    r"\bdevops\b",
    r"security\s*engineer",
    r"threat\s*intelligence",
    r"transmission\s*line",
    r"scraping",
    r"labeling",
    r"labelling",
    r"intern\b",
    r"freelance",
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\bdirector\b",
    r"\bvp\b",
    r"\bchief\b",
    r"\bhead\s+of\b",
)

DEFAULT_SENIOR_PATTERNS: tuple[str, ...] = (
    r"\bsenior\b",
    r"\bsr\.?\b",
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\blead\b",
    r"\bdirector\b",
    r"\bvp\b",
    r"\bchief\b",
    r"\bhead\s+of\b",
    r"\bmanager\b",
)


def _compile_patterns(patterns: Iterable[str]) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.I)


def _load_patterns() -> tuple[re.Pattern[str], re.Pattern[str], re.Pattern[str]]:
    config = load_config()
    include = config.get("title_include_patterns") or list(DEFAULT_INCLUDE_PATTERNS)
    exclude = config.get("title_exclude_patterns") or list(DEFAULT_EXCLUDE_PATTERNS)
    senior = config.get("senior_title_patterns") or list(DEFAULT_SENIOR_PATTERNS)
    return (
        _compile_patterns(include),
        _compile_patterns(exclude),
        _compile_patterns(senior),
    )


_INCLUDE_RE, _EXCLUDE_RE, _SENIOR_RE = _load_patterns()


def is_data_engineering_title(title: Optional[str]) -> bool:
    """Return True only for data-engineering job titles."""
    if not isinstance(title, str) or not title.strip():
        return False
    text = title.strip()
    if _EXCLUDE_RE.search(text):
        return False
    return bool(_INCLUDE_RE.search(text))


def is_senior_title(title: Optional[str]) -> bool:
    if not isinstance(title, str) or not title.strip():
        return False
    return bool(_SENIOR_RE.search(title.strip()))


def filter_data_engineering_jobs(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows whose titles are not data-engineering roles."""
    if df.empty or "title" not in df.columns:
        return df
    mask = df["title"].map(is_data_engineering_title)
    return df.loc[mask].copy()


def filter_senior_titles(df: pd.DataFrame) -> pd.DataFrame:
    """Drop senior/staff/principal/lead-style titles."""
    if df.empty or "title" not in df.columns:
        return df
    mask = ~df["title"].map(is_senior_title)
    return df.loc[mask].copy()
