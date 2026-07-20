import pandas as pd

from jobfetcher.analyzer import calculate_match_score, enrich_jobs_dataframe, filter_experience_band


def test_match_score_prefers_skill_and_band_fit():
    good = pd.Series(
        {
            "title": "Data Engineer",
            "description": "2-4 years python sql snowflake dbt spark airflow aws",
            "est_min_years": 2,
            "est_max_years": 4,
            "is_mid_level": True,
            "is_fortune_500": False,
        }
    )
    bad = pd.Series(
        {
            "title": "Staff Data Engineer",
            "description": "10+ years java only",
            "est_min_years": 10,
            "est_max_years": None,
            "is_mid_level": False,
            "is_fortune_500": False,
        }
    )
    assert calculate_match_score(good) > calculate_match_score(bad)


def test_filter_experience_band_keeps_overlap():
    df = pd.DataFrame(
        [
            {"title": "Data Engineer", "est_min_years": 2, "est_max_years": 4},
            {"title": "Data Engineer", "est_min_years": 8, "est_max_years": None},
            {"title": "Data Engineer", "est_min_years": None, "est_max_years": None},
        ]
    )
    filtered = filter_experience_band(df, band_min=2, band_max=4, keep_unknown=True)
    assert len(filtered) == 2
    assert 8 not in set(filtered["est_min_years"].dropna().astype(int))


def test_enrich_adds_match_score():
    df = pd.DataFrame(
        [
            {
                "job_url": "https://example.com/1",
                "title": "Data Engineer",
                "company": "Acme",
                "description": "3 years python sql spark aws",
            }
        ]
    )
    enriched = enrich_jobs_dataframe(df)
    assert "match_score" in enriched.columns
    assert "matched_skills" in enriched.columns
    assert "est_min_years" in enriched.columns
    assert "in_experience_band" in enriched.columns
    assert bool(enriched.iloc[0]["in_experience_band"]) is True
