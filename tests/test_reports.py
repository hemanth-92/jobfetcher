import pandas as pd

from jobfetcher.reports import write_jobs_html


def test_write_jobs_html(tmp_path):
    df = pd.DataFrame(
        [
            {
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
                "site": "remotive",
                "source_location": "Remote",
                "source_query": "data engineer",
                "is_fortune_500": False,
                "is_mid_level": True,
                "mid_level_score": 5.0,
                "match_score": 12.5,
                "matched_skills": "python, sql",
                "est_min_years": 3,
                "est_max_years": 5,
                "is_remote": True,
                "job_url": "https://example.com/jobs/1",
            }
        ]
    )

    html_path = tmp_path / "jobs.html"
    write_jobs_html(df, str(html_path), default_min_years=2, default_max_years=4)

    html_content = html_path.read_text(encoding="utf-8")

    assert 'href="https://example.com/jobs/1"' in html_content
    assert "Data Engineer" in html_content
    assert 'id="q"' in html_content
    assert 'id="site"' in html_content
    assert 'id="mid"' in html_content
    assert "data-search=" in html_content
    assert "applyFilters" in html_content
    assert "localStorage" in html_content
    assert "exportVisibleCsv" in html_content
    assert "My profile" in html_content
    assert "Show all" in html_content
    assert "btn-primary" in html_content
    assert "btn-group" in html_content
    assert "filters-grid" in html_content
    assert "toolbar" in html_content
    assert "soft mode" in html_content
    assert "12.5" in html_content
    assert "remotive" in html_content
