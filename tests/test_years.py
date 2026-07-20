import pytest

from jobfetcher.years import estimate_years, overlaps_experience_band


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3-5 years of experience", {"min": 3, "max": 5}),
        ("5+ years", {"min": 5, "max": None}),
        ("5 years", {"min": 5, "max": None}),
        ("minimum 3 years", {"min": 3, "max": None}),
        ("at least 2 years of experience", {"min": 2, "max": None}),
        ("3 to 5 years", {"min": 3, "max": 5}),
        ("2–4 years experience required", {"min": 2, "max": 4}),
        ("Requires 2+ years of experience with Python", {"min": 2, "max": None}),
        ("", {"min": None, "max": None}),
        (None, {"min": None, "max": None}),
        ("Company is 170 years old in the market", {"min": None, "max": None}),
        ("Salary 15 LPA and 170 years company history", {"min": None, "max": None}),
    ],
)
def test_estimate_years(text, expected):
    assert estimate_years(text) == expected


def test_estimate_years_caps_unreasonable_values():
    result = estimate_years("Need 99 years of experience")
    assert result["min"] is None


@pytest.mark.parametrize(
    ("est_min", "est_max", "expected"),
    [
        (2, 4, True),
        (3, None, True),
        (5, None, False),
        (1, 1, False),
        (None, None, True),  # keep unknown by default
        (4, 6, True),  # min within band
        (0, 3, True),  # overlaps band
    ],
)
def test_overlaps_experience_band(est_min, est_max, expected):
    assert overlaps_experience_band(est_min, est_max, 2, 4, keep_unknown=True) is expected


def test_overlaps_drops_unknown_when_configured():
    assert overlaps_experience_band(None, None, 2, 4, keep_unknown=False) is False
