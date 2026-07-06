import pandas as pd

from jobfetcher.analyzer import ProfileFilter, enrich_jobs_dataframe, filter_profile_matches


def test_filter_profile_matches_snowflake_and_experience_band():
    df = enrich_jobs_dataframe(
        pd.DataFrame(
            [
                {
                    "job_url": "https://example.com/1",
                    "title": "Snowflake Data Engineer",
                    "description": "2+ years with snowflake, sql, python",
                },
                {
                    "job_url": "https://example.com/2",
                    "title": "Senior Snowflake Engineer",
                    "description": "8+ years snowflake leadership",
                },
                {
                    "job_url": "https://example.com/3",
                    "title": "Data Engineer",
                    "description": "python sql only",
                },
            ]
        )
    )
    profile = ProfileFilter(skills=("snowflake",), min_years=2, max_years=6)
    matches = filter_profile_matches(df, profile)

    assert len(matches) == 1
    assert matches.iloc[0]["job_url"] == "https://example.com/1"