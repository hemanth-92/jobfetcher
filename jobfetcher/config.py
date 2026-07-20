"""Shared configuration loading for jobfetcher."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "fortune_500_companies": [],
    "key_skills": [],
    "experience_min": 2,
    "experience_max": 4,
    "keep_unknown_years": True,
    # Soft approach: rank and filter in HTML; do not hard-drop by years/seniority
    "filter_experience_band": False,
    "exclude_senior_titles": False,
    "my_skills": ["python", "sql", "snowflake", "dbt", "spark", "airflow", "aws", "etl"],
    "must_skills": ["python", "sql"],
    "nice_skills": [
        "snowflake",
        "dbt",
        "spark",
        "airflow",
        "aws",
        "azure",
        "gcp",
        "kafka",
        "docker",
        "etl",
    ],
    "search_terms": ["data engineer", "analytics engineer", "etl engineer"],
    "locations": ["India", "Remote"],
    "remote_locations": ["India", "Remote"],
    "title_include_patterns": [],
    "title_exclude_patterns": [],
}


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load configuration from JSON, defaulting to the project-root config.json."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged.update(data)
        return merged
    except FileNotFoundError:
        logger.warning("Config file not found at %s; using defaults", config_path)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in config %s: %s", config_path, e)
    except OSError as e:
        logger.error("Failed to read config %s: %s", config_path, e)
    return DEFAULT_CONFIG.copy()
