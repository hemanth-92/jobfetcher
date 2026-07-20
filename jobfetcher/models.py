import logging
from typing import Any, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, HttpUrl, ValidationError

from .dedupe import normalize_job_url

logger = logging.getLogger(__name__)


def _coerce_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return bool(value)


class Job(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    job_url: HttpUrl
    title: str
    company: Optional[str] = "Unknown"
    location: Optional[str] = "Unknown"
    date_posted: Optional[str] = None
    description: Optional[str] = ""
    site: Optional[str] = None
    source_query: Optional[str] = None
    source_location: Optional[str] = None
    is_remote: bool = False
    job_type: Optional[str] = None
    is_fortune_500: bool = False

    # Analysis fields
    est_min_years: Optional[int] = None
    est_max_years: Optional[int] = None


def normalize_job_record(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Validate and normalize a raw job record from any source."""
    job_url = record.get("job_url") or record.get("url")
    title = record.get("title")
    if not job_url or not title:
        return None

    payload = {
        "job_url": normalize_job_url(job_url) or str(job_url).strip(),
        "title": str(title).strip(),
        "company": _coerce_optional_str(record.get("company")) or "Unknown",
        "location": _coerce_optional_str(record.get("location")) or "Unknown",
        "date_posted": _coerce_optional_str(record.get("date_posted")),
        "description": _coerce_optional_str(record.get("description")) or "",
        "site": _coerce_optional_str(record.get("site")),
        "source_query": _coerce_optional_str(record.get("source_query")),
        "source_location": _coerce_optional_str(record.get("source_location")),
        "is_remote": _coerce_bool(record.get("is_remote")),
        "job_type": _coerce_optional_str(record.get("job_type")),
        "is_fortune_500": _coerce_bool(record.get("is_fortune_500")),
    }

    try:
        job = Job.model_validate(payload)
        return job.model_dump(mode="json")
    except ValidationError as exc:
        logger.debug("Skipping invalid job record (%s): %s", title, exc)
        return None


def validate_jobs_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Drop invalid rows and normalize valid jobs to a consistent schema."""
    if df.empty:
        return df

    validated: list[dict[str, Any]] = []
    for record in df.to_dict(orient="records"):
        normalized = normalize_job_record(record)
        if normalized is not None:
            validated.append(normalized)

    dropped = len(df) - len(validated)
    if dropped:
        logger.warning("Dropped %d job records during validation", dropped)

    if not validated:
        return pd.DataFrame()

    return pd.DataFrame(validated)
