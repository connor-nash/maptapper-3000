import json

from database import compute_daily_highlights


def row(name: str, rounds: list[int]) -> dict:
    weights = [1, 1, 2, 3, 3]
    return {"username": name, "round_scores": json.dumps(rounds),
            "final_score": sum(r * w for r, w in zip(rounds, weights))}


def test_shot_rewards_beating_the_field_on_a_hard_round_over_a_common_100():
    scores = [
        row("Ace", [100, 100, 100, 50, 100]),
        row("Zach", [90, 90, 90, 85, 90]),
        row("Dave", [100, 100, 100, 54, 100]),
    ]
    shot = compute_daily_highlights(scores)["shot"]
    assert (shot["username"], shot["round"]) == ("Zach", 4)
    assert shot["group_avg"] == 52
    assert shot["value"] == (85 - 52) * 3


def test_whiff_is_costliest_miss_after_round_weighting():
    scores = [
        row("Low R1", [20, 100, 100, 100, 100]),
        row("Low R5", [100, 100, 100, 100, 40]),
    ]
    whiff = compute_daily_highlights(scores)["whiff"]
    assert (whiff["username"], whiff["round"], whiff["cost"]) == ("Low R5", 5, 180)


def test_solo_player_gets_no_shot_but_can_whiff():
    h = compute_daily_highlights([row("Solo", [100, 100, 100, 100, 90])])
    assert h["shot"] is None
    assert h["whiff"]["cost"] == 30


def test_all_perfect_day_has_no_whiff_or_shot():
    h = compute_daily_highlights([row("A", [100] * 5), row("B", [100] * 5)])
    assert h["shot"] is None
    assert h["whiff"] is None


def test_group_numbers_and_hardest_round():
    a, b = row("A", [90, 80, 70, 60, 40]), row("B", [90, 80, 70, 60, 60])
    h = compute_daily_highlights([a, b])
    assert h["player_count"] == 2
    assert (h["hardest_round"], h["hardest_round_avg"]) == (5, 50)
    assert h["group_avg"] == (a["final_score"] + b["final_score"]) / 2
