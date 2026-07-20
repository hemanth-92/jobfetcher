"""Parse years-of-experience requirements from job text."""
from __future__ import annotations

import re
from typing import Dict, Optional

# Reasonable cap — values above this are almost always parser noise
MAX_REASONABLE_YEARS = 20

# Prefer experience-related phrasing; order matters (more specific first).
_YEAR_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"(?:minimum|min\.?|at\s+least|over|more\s+than|no\s+less\s+than)\s+(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b",
        r"(\d{1,2})\s*\+\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp\.?)\b",
        r"(\d{1,2})\s*\+\s*(?:years?|yrs?)\b",
        r"(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s*(?:years?|yrs?)\b",
        r"(\d{1,2})\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp\.?)\b",
        r"(?:experience|exp\.?)[^\n.]{0,40}?(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s*(?:years?|yrs?)\b",
        r"(?:experience|exp\.?)[^\n.]{0,40}?(\d{1,2})\s*\+?\s*(?:years?|yrs?)\b",
        r"(\d{1,2})\s*(?:years?|yrs?)\b",
    )
)

# Drop matches that are clearly not YoE (company age, compensation, etc.)
_NOISE_NEARBY = re.compile(
    r"(company|founded|established|history|old|salary|ctc|lpa|lakhs?|crore|"
    r"employees?|headcount|customers?|users?|million|billion|revenue)",
    re.I,
)


def _clamp(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    if value < 0 or value > MAX_REASONABLE_YEARS:
        return None
    return value


def estimate_years(text: str) -> Dict[str, Optional[int]]:
    """Estimate minimum and maximum years of experience from job text.

    Returns {"min": int|None, "max": int|None}. Values above MAX_REASONABLE_YEARS
    are discarded as noise.
    """
    if not isinstance(text, str) or not text.strip():
        return {"min": None, "max": None}

    # Limit scan to first portion of description (requirements usually appear early)
    sample = text[:4000]

    candidates: list[tuple[int, Optional[int], int]] = []  # min, max, priority
    for priority, pattern in enumerate(_YEAR_PATTERNS):
        for match in pattern.finditer(sample):
            start = max(0, match.start() - 40)
            end = min(len(sample), match.end() + 40)
            window = sample[start:end]
            if _NOISE_NEARBY.search(window):
                continue

            groups = [g for g in match.groups() if g is not None]
            if not groups:
                continue
            try:
                first = int(groups[0])
            except (TypeError, ValueError):
                continue
            second: Optional[int] = None
            if len(groups) > 1:
                try:
                    second = int(groups[1])
                except (TypeError, ValueError):
                    second = None

            if second is not None:
                lo, hi = sorted((first, second))
            else:
                lo, hi = first, None

            lo = _clamp(lo)
            hi = _clamp(hi)
            if lo is None and hi is None:
                continue
            # Prefer specific patterns and earlier matches
            candidates.append((lo if lo is not None else hi or 0, hi, priority))

    if not candidates:
        return {"min": None, "max": None}

    # Lowest priority number first, then earliest-friendly by keeping first among ties
    candidates.sort(key=lambda item: (item[2], item[0]))
    best_min, best_max, _ = candidates[0]
    if best_max is not None and best_min is not None and best_max < best_min:
        best_min, best_max = best_max, best_min
    return {"min": best_min, "max": best_max}


def overlaps_experience_band(
    est_min: Optional[float],
    est_max: Optional[float],
    band_min: int = 2,
    band_max: int = 4,
    keep_unknown: bool = True,
) -> bool:
    """Return True if the job's experience requirement overlaps [band_min, band_max]."""
    min_y = int(est_min) if est_min is not None and str(est_min) != "nan" else None
    max_y = int(est_max) if est_max is not None and str(est_max) != "nan" else None

    try:
        import math

        if min_y is not None and isinstance(est_min, float) and math.isnan(est_min):
            min_y = None
        if max_y is not None and isinstance(est_max, float) and math.isnan(est_max):
            max_y = None
    except (TypeError, ValueError):
        pass

    if min_y is None and max_y is None:
        return keep_unknown

    # Job requires more than the candidate band can offer
    if min_y is not None and min_y > band_max:
        return False

    # Job is only for people below the band (e.g. 0-1 years)
    if max_y is not None and max_y < band_min:
        return False

    return True
