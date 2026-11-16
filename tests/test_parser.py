from datetime import date

import pytest

import parser as maptap_parser
from parser import parse_maptap_share


def share(month_day: str, rounds: str, final: int) -> str:
    return f"www.maptap.gg {month_day}\n{rounds}\nFinal score: {final}"


@pytest.fixture
def today(monkeypatch):
    def set_today(d: date):
        monkeypatch.setattr(maptap_parser, "mt_today", lambda: d)
    return set_today


def test_parses_valid_share(today):
    today(date(2026, 7, 20))
    parsed = parse_maptap_share(share("July 20", "88🎉 96🔥 97🔥 97😱 7😱", 690))
    assert parsed.game_date == "2026-07-20"
    assert parsed.round_scores == [88, 96, 97, 97, 7]
    assert parsed.final_score == 690


def test_dec_31_game_pasted_on_jan_1_stays_in_old_year(today):
    today(date(2027, 1, 1))
    parsed = parse_maptap_share(share("December 31", "100 100 100 100 100", 1000))
    assert parsed.game_date == "2026-12-31"


def test_jan_1_game_pasted_late_on_dec_31_goes_to_new_year(today):
    today(date(2026, 12, 31))
    parsed = parse_maptap_share(share("Jan 1", "100 100 100 100 100", 1000))
    assert parsed.game_date == "2027-01-01"


def test_feb_29_resolves_to_leap_year(today):
    today(date(2029, 1, 2))
    parsed = parse_maptap_share(share("Feb 29", "100 100 100 100 100", 1000))
    assert parsed.game_date == "2028-02-29"


def test_rejects_final_score_that_does_not_match_rounds(today):
    today(date(2026, 7, 20))
    assert parse_maptap_share(share("July 20", "88 96 97 97 7", 1000)) is None


def test_rejects_out_of_range_round(today):
    today(date(2026, 7, 20))
    assert parse_maptap_share(share("July 20", "101 96 97 97 7", 697)) is None


def test_rejects_unknown_month(today):
    today(date(2026, 7, 20))
    assert parse_maptap_share(share("Smarch 20", "88 96 97 97 7", 690)) is None
