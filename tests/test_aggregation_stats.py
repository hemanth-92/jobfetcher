import pandas as pd
from unittest.mock import patch

from jobfetcher.aggregator import aggregate_jobs


def _sample_jobs() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "job_url": "https://example.com/jobs/1",
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
                "description": "python sql",
                "site": "remotive",
                "source_query": "data engineer",
                "source_location": "Remote",
            },
            {
                "job_url": "https://example.com/jobs/2",
                "title": "Analytics Engineer",
                "company": "Beta",
                "location": "Remote",
                "description": "python sql",
                "site": "remotive",
                "source_query": "data engineer",
                "source_location": "Remote",
            },
        ]
    )


@patch("jobfetcher.aggregator._collect_query_task")
def test_aggregate_jobs_skips_seen_urls(mock_collect, tmp_path):
    seen_file = tmp_path / "seen_jobs.json"
    seen_file.write_text('["https://example.com/jobs/1"]', encoding="utf-8")
    mock_collect.return_value = _sample_jobs()

    jobs = aggregate_jobs(
        search_terms=["data engineer"],
        locations=["Remote"],
        site_names=["remotive"],
        seen_file=str(seen_file),
        top_n=10,
        max_workers=1,
    )

    assert len(jobs) == 1
    assert jobs.iloc[0]["job_url"] == "https://example.com/jobs/2"


@patch("jobfetcher.aggregator._collect_query_task")
def test_aggregate_jobs_include_seen_returns_tracked_jobs(mock_collect, tmp_path):
    seen_file = tmp_path / "seen_jobs.json"
    seen_file.write_text('["https://example.com/jobs/1"]', encoding="utf-8")
    mock_collect.return_value = _sample_jobs()

    jobs = aggregate_jobs(
        search_terms=["data engineer"],
        locations=["Remote"],
        site_names=["remotive"],
        seen_file=str(seen_file),
        top_n=10,
        max_workers=1,
        include_seen=True,
    )

    assert len(jobs) == 2
    assert set(jobs["job_url"]) == {
        "https://example.com/jobs/1",
        "https://example.com/jobs/2",
    }