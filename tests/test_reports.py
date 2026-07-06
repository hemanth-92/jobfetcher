import pandas as pd

from jobfetcher.reports import write_jobs_html, write_jobs_links_csv


def test_write_jobs_links_csv_and_html(tmp_path):
    df = pd.DataFrame(
        [
            {
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
                "site": "remotive",
                "source_location": "Remote",
                "is_fortune_500": False,
                "is_mid_level": True,
                "mid_level_score": 5.0,
                "est_min_years": 3,
                "est_max_years": 5,
                "job_url": "https://example.com/jobs/1",
            }
        ]
    )

    csv_path = tmp_path / "links.csv"
    html_path = tmp_path / "jobs.html"
    write_jobs_links_csv(df, str(csv_path))
    write_jobs_html(df, str(html_path))

    csv_content = csv_path.read_text(encoding="utf-8")
    html_content = html_path.read_text(encoding="utf-8")

    assert "https://example.com/jobs/1" in csv_content
    assert 'href="https://example.com/jobs/1"' in html_content
    assert "Data Engineer" in html_content