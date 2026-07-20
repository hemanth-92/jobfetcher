import pandas as pd

from jobfetcher.analyzer import AnalyzerOutputs, run_market_analysis


def test_analyzer_creates_nested_output_directory(tmp_path):
    input_csv = tmp_path / "jobs.csv"
    nested_dir = tmp_path / "results"
    outputs = AnalyzerOutputs(
        links_html=str(nested_dir / "jobs.html"),
        summary_json=str(nested_dir / "market_summary.json"),
    )

    pd.DataFrame(
        [
            {
                "job_url": "https://example.com/1",
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
                "description": "3 years python sql spark aws airflow dbt",
            }
        ]
    ).to_csv(input_csv, index=False)

    run_market_analysis(input_csv=str(input_csv), outputs=outputs)

    assert nested_dir.exists()
    assert (nested_dir / "jobs.html").exists()
    assert (nested_dir / "market_summary.json").exists()


def test_analyzer_writes_custom_output_paths(tmp_path):
    input_csv = tmp_path / "jobs.csv"
    outputs = AnalyzerOutputs(
        links_html=str(tmp_path / "browse.html"),
        summary_json=str(tmp_path / "summary.json"),
    )

    pd.DataFrame(
        [
            {
                "job_url": "https://example.com/1",
                "title": "Data Engineer",
                "company": "Acme",
                "location": "Remote",
                "description": "3 years python sql spark aws airflow dbt",
            }
        ]
    ).to_csv(input_csv, index=False)

    run_market_analysis(input_csv=str(input_csv), outputs=outputs)

    assert (tmp_path / "browse.html").exists()
    assert (tmp_path / "summary.json").exists()
    # Only the two analyzer deliverables — no legacy side files
    assert not (tmp_path / "mid.csv").exists()
    assert not (tmp_path / "summary.txt").exists()
