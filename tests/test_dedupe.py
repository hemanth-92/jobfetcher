import pandas as pd

from jobfetcher.dedupe import dedupe_jobs, job_fingerprint, normalize_job_url


def test_normalize_job_url_strips_tracking():
    url = "https://www.linkedin.com/jobs/view/123/?utm_source=x&utm_medium=y&refId=abc"
    cleaned = normalize_job_url(url)
    assert "utm_source" not in cleaned
    assert "refId" not in cleaned
    assert cleaned.endswith("/jobs/view/123") or cleaned.endswith("/jobs/view/123/")


def test_job_fingerprint_normalizes_text():
    a = job_fingerprint("Senior Data Engineer!", "Acme Inc.", "Bengaluru, India")
    b = job_fingerprint("senior data engineer", "acme inc", "bengaluru india")
    assert a == b


def test_dedupe_jobs_by_url_and_fingerprint():
    df = pd.DataFrame(
        [
            {
                "job_url": "https://example.com/jobs/1?utm_source=x",
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
            },
            {
                "job_url": "https://example.com/jobs/1",
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
            },
            {
                "job_url": "https://example.com/jobs/2",
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
            },
            {
                "job_url": "https://example.com/jobs/3",
                "title": "Analytics Engineer",
                "company": "Beta",
                "location": "India",
            },
        ]
    )
    out = dedupe_jobs(df)
    assert len(out) == 2
    assert set(out["title"]) == {"Data Engineer", "Analytics Engineer"}
