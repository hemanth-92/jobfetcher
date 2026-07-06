import pandas as pd
import pytest

from jobfetcher.analyzer import (
    calculate_mid_level_score,
    estimate_years,
    is_mid_level_job,
)
from jobfetcher.config import DEFAULT_CONFIG_PATH, load_config


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3-5 years of experience", {"min": 3, "max": 5}),
        ("5+ years", {"min": 5, "max": None}),
        ("5 years", {"min": 5, "max": None}),
        ("minimum 3 years", {"min": 3, "max": None}),
        ("3 to 5 years", {"min": 3, "max": 5}),
        ("", {"min": None, "max": None}),
        (None, {"min": None, "max": None}),
    ],
)
def test_estimate_years(text, expected):
    assert estimate_years(text) == expected


def test_calculate_mid_level_score_prefers_data_engineer():
    score = calculate_mid_level_score(
        "Data Engineer",
        "python sql spark aws airflow dbt kafka terraform",
    )
    assert score >= 4.0


def test_calculate_mid_level_score_penalizes_senior_title():
    junior_score = calculate_mid_level_score("Data Engineer", "python sql spark")
    senior_score = calculate_mid_level_score("Senior Data Engineer", "python sql spark")
    assert senior_score < junior_score


def test_is_mid_level_job_true_for_strong_match():
    row = pd.Series(
        {
            "title": "Data Engineer",
            "description": "3 years experience with python, sql, spark, aws, airflow, dbt",
        }
    )
    assert is_mid_level_job(row) is True


def test_is_mid_level_job_false_for_senior_role():
    row = pd.Series(
        {
            "title": "Principal Data Engineer",
            "description": "12+ years leading large data platform teams",
        }
    )
    assert is_mid_level_job(row) is False


def test_load_config_reads_project_config():
    config = load_config(DEFAULT_CONFIG_PATH)
    assert "key_skills" in config
    assert "fortune_500_companies" in config
    assert len(config["key_skills"]) > 0