import pandas as pd
import pytest

from jobfetcher.title_filter import (
    filter_data_engineering_jobs,
    filter_senior_titles,
    is_data_engineering_title,
    is_senior_title,
)


@pytest.mark.parametrize(
    "title",
    [
        "Data Engineer",
        "Senior Data Engineer",
        "Analytics Engineer",
        "ETL Engineer",
        "ETL Developer",
        "Data Pipeline Engineer",
        "Big Data Engineer",
        "Data Platform Engineer",
        "Snowflake Engineer",
        "Cloud Data Engineer",
        "AWS Data Engineer",
        "Database Engineer",
        "Data Architect",
    ],
)
def test_keeps_data_engineering_titles(title):
    assert is_data_engineering_title(title) is True


@pytest.mark.parametrize(
    "title",
    [
        "Backend Engineer",
        "Intermediate Backend Engineer - Analytics Instrumentation",
        "Frontend Developer",
        "Full Stack Engineer",
        "Staff Fullstack Engineer - Data Products",
        "Software Engineer",
        "Senior Software Engineer",
        "Data Analyst",
        "Data Scientist",
        "Machine Learning Engineer",
        "Sales Engineer",
        "Senior DevOps Engineer",
        "Product Engineer",
        "Freelance Data Scraping Engineer (Python)",
        "Data Science INTERN",
    ],
)
def test_drops_non_data_engineering_titles(title):
    assert is_data_engineering_title(title) is False


def test_filter_data_engineering_jobs_dataframe():
    df = pd.DataFrame(
        {
            "title": [
                "Data Engineer",
                "Backend Engineer",
                "Analytics Engineer",
                "Frontend Developer",
            ],
            "job_url": [
                "https://example.com/1",
                "https://example.com/2",
                "https://example.com/3",
                "https://example.com/4",
            ],
        }
    )
    filtered = filter_data_engineering_jobs(df)
    assert list(filtered["title"]) == ["Data Engineer", "Analytics Engineer"]


def test_filter_senior_titles():
    assert is_senior_title("Senior Data Engineer") is True
    assert is_senior_title("Data Engineer") is False
    df = pd.DataFrame({"title": ["Data Engineer", "Senior Data Engineer", "Staff Data Engineer"]})
    filtered = filter_senior_titles(df)
    assert list(filtered["title"]) == ["Data Engineer"]
