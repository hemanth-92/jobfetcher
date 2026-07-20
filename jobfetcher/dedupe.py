"""Normalize job URLs and build dedup fingerprints."""
from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "refId",
    "trackingId",
    "trk",
    "trkInfo",
    "originalSubdomain",
    "original_referer",
}


def normalize_job_url(url: Any) -> str:
    """Strip tracking params and normalize scheme/host/path for dedup."""
    if url is None:
        return ""
    text = str(url).strip()
    if not text:
        return ""
    try:
        parsed = urlparse(text)
    except ValueError:
        return text

    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in TRACKING_PARAMS and not key.lower().startswith("utm_")
    ]
    # Drop trailing slash differences except root
    path = parsed.path.rstrip("/") or "/"
    cleaned = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=path,
        params="",
        query=urlencode(query, doseq=True),
        fragment="",
    )
    return urlunparse(cleaned)


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def job_fingerprint(
    title: Any,
    company: Any = None,
    location: Any = None,
) -> str:
    """Fingerprint used to collapse the same role posted under different URLs."""
    return "|".join(
        [
            _norm_text(company),
            _norm_text(title),
            _norm_text(location),
        ]
    )


def dedupe_jobs(df: pd.DataFrame) -> pd.DataFrame:
    """Deduplicate by normalized URL, then by company+title+location fingerprint."""
    if df.empty:
        return df

    out = df.copy()
    if "job_url" in out.columns:
        out["job_url"] = out["job_url"].map(normalize_job_url)
        out = out.drop_duplicates(subset=["job_url"], keep="first")

    if all(col in out.columns for col in ("title", "company")):
        location_col = "location" if "location" in out.columns else None
        out["_fingerprint"] = out.apply(
            lambda row: job_fingerprint(
                row.get("title"),
                row.get("company"),
                row.get(location_col) if location_col else None,
            ),
            axis=1,
        )
        # Only fingerprint-dedup when company is known (avoid collapsing Unknowns)
        known = out["company"].fillna("").astype(str).str.lower().ne("unknown")
        known &= out["_fingerprint"].str.len() > 2
        first_known = out.loc[known].drop_duplicates(subset=["_fingerprint"], keep="first")
        unknown = out.loc[~known]
        out = pd.concat([first_known, unknown], ignore_index=True)
        out = out.drop(columns=["_fingerprint"], errors="ignore")

    return out.reset_index(drop=True)
