import pandas as pd

from jobfetcher.analyzer import AnalyzerOutputs, run_market_analysis


def test_analyzer_creates_nested_output_directory(tmp_path):
    input_csv = tmp_path / "jobs.csv"
    nested_dir = tmp_path / "results"
    outputs = AnalyzerOutputs(
        mid_csv=str(nested_dir / "mid.csv"),
        mid_jsonl=str(nested_dir / "mid.jsonl"),
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
    assert (nested_dir / "mid.csv").exists()
    assert (nested_dir / "mid.jsonl").exists()


def test_analyzer_writes_custom_output_paths(tmp_path):
    input_csv = tmp_path / "jobs.csv"
    outputs = AnalyzerOutputs(
        mid_csv=str(tmp_path / "mid.csv"),
        mid_jsonl=str(tmp_path / "mid.jsonl"),
        summary_json=str(tmp_path / "summary.json"),
        summary_txt=str(tmp_path / "summary.txt"),
        recurrence_file=str(tmp_path / "keywords.json"),
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

    assert (tmp_path / "mid.csv").exists()
    assert (tmp_path / "mid.jsonl").exists()
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "summary.txt").exists()
    assert (tmp_path / "keywords.json").exists()