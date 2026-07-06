import datetime

import pandas as pd

from jobfetcher.models import Job, normalize_job_record, validate_jobs_dataframe


def test_normalize_job_record_accepts_url_alias():
    record = normalize_job_record(
        {
            "url": "https://example.com/jobs/1",
            "title": "Data Engineer",
            "company": "Acme",
        }
    )
    assert record is not None
    assert record["job_url"] == "https://example.com/jobs/1"
    assert record["title"] == "Data Engineer"


def test_normalize_job_record_rejects_missing_title():
    assert normalize_job_record({"job_url": "https://example.com/jobs/1"}) is None


def test_validate_jobs_dataframe_drops_invalid_rows():
    df = pd.DataFrame(
        [
            {"job_url": "https://example.com/1", "title": "Data Engineer"},
            {"job_url": "not-a-url", "title": "Broken Job"},
            {"title": "Missing URL"},
        ]
    )
    validated = validate_jobs_dataframe(df)
    assert len(validated) == 1
    assert validated.iloc[0]["title"] == "Data Engineer"


def test_normalize_job_record_handles_linkedin_date_posted():
    record = normalize_job_record(
        {
            "job_url": "https://www.linkedin.com/jobs/view/123",
            "title": "Data Engineer",
            "company": "Acme",
            "date_posted": datetime.date(2026, 7, 3),
            "site": "linkedin",
        }
    )
    assert record is not None
    assert record["date_posted"] == "2026-07-03"
    assert record["site"] == "linkedin"


def test_job_model_defaults():
    job = Job(job_url="https://example.com/job", title="ETL Engineer")
    assert job.company == "Unknown"
    assert job.is_remote is False