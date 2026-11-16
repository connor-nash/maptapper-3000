from datetime import date

from cogs.stats import current_streak

TODAY = date(2026, 11, 15)


def dates(*days: int) -> set[str]:
    return {date(2026, 11, d).isoformat() for d in days}


def test_consecutive_days_including_today():
    assert current_streak(dates(15, 14, 13), TODAY) == 3


def test_streak_still_alive_if_today_not_played_yet():
    assert current_streak(dates(14, 13, 12), TODAY) == 3


def test_every_other_day_is_not_a_streak():
    assert current_streak(dates(15, 13, 11), TODAY) == 1


def test_gap_breaks_streak():
    assert current_streak(dates(15, 14, 12, 11, 10), TODAY) == 2


def test_last_played_two_days_ago_is_zero():
    assert current_streak(dates(13, 12), TODAY) == 0


def test_no_games():
    assert current_streak(set(), TODAY) == 0
