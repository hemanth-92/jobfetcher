import pandas as pd

from jobfetcher.analyzer import AnalyzerOutputs, enrich_jobs_dataframe, run_market_analysis


def test_enrich_jobs_dataframe_adds_market_fields():
    df = pd.DataFrame(
        [
            {
                "title": "Data Engineer",
                "description": "3 years python sql spark aws airflow dbt",
                "job_url": "https://example.com/1",
            }
        ]
    )
    enriched = enrich_jobs_dataframe(df)
    assert "mid_level_score" in enriched.columns
    assert "is_mid_level" in enriched.columns
    assert "est_min_years" in enriched.columns
    assert bool(enriched.iloc[0]["is_mid_level"]) is True


def test_run_market_analysis_writes_reports(tmp_path):
    input_csv = tmp_path / "jobs.csv"
    outputs = AnalyzerOutputs(
        links_html=str(tmp_path / "jobs.html"),
        summary_json=str(tmp_path / "market_summary.json"),
    )

    pd.DataFrame(
        [
            {
                "job_url": "https://example.com/1",
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
                "site": "remotive",
                "source_location": "Remote",
                "description": "3 years python sql spark aws airflow dbt",
            },
            {
                "job_url": "https://example.com/2",
                "title": "Senior Data Engineer",
                "company": "Beta",
                "location": "Remote",
                "site": "linkedin",
                "source_location": "Remote",
                "description": "12+ years leading teams",
            },
        ]
    ).to_csv(input_csv, index=False)

    enriched = run_market_analysis(input_csv=str(input_csv), outputs=outputs)
    summary = (tmp_path / "market_summary.json").read_text(encoding="utf-8")

    # Soft mode: keep both roles; rank ideal fits higher via match_score
    assert len(enriched) == 2
    assert "match_score" in enriched.columns
    assert "in_experience_band" in enriched.columns
    de = enriched[enriched["title"] == "Data Engineer"].iloc[0]
    senior = enriched[enriched["title"] == "Senior Data Engineer"].iloc[0]
    assert de["match_score"] > senior["match_score"]
    assert bool(de["in_experience_band"]) is True
    assert bool(senior["in_experience_band"]) is False
    assert (tmp_path / "jobs.html").exists()
    assert (tmp_path / "market_summary.json").exists()
    assert not (tmp_path / "jobs_links.csv").exists()
    assert not (tmp_path / "market_summary.txt").exists()
    assert not (tmp_path / "mid_jobs.csv").exists()
    assert '"total_jobs": 2' in summary
