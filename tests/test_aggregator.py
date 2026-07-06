import pandas as pd

from jobfetcher.aggregator import ADZUNA_COUNTRY_CURRENCY, append_trend_log


def test_adzuna_currency_mapping():
    assert ADZUNA_COUNTRY_CURRENCY["us"] == "USD"
    assert ADZUNA_COUNTRY_CURRENCY["in"] == "INR"
    assert ADZUNA_COUNTRY_CURRENCY["gb"] == "GBP"
    assert ADZUNA_COUNTRY_CURRENCY["bd"] == "BDT"


def test_append_trend_log_without_fortune_column(tmp_path):
    jobs = pd.DataFrame(
        {
            "title": ["Data Engineer"],
            "company": ["Acme"],
            "location": ["Remote"],
            "source_location": ["India"],
            "description": ["python sql spark"],
        }
    )
    log_path = tmp_path / "trends.log"
    append_trend_log(jobs, path=str(log_path))
    content = log_path.read_text(encoding="utf-8")
    assert "Total jobs: 1" in content
    assert "Fortune 500 jobs: 0" in content