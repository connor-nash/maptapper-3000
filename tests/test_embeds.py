import json

import embeds

DISCORD_EMBED_TOTAL_LIMIT = 6000


def score_row(i: int) -> dict:
    return {
        "username": f"PlayerWithAVeryLongName{i:02d}",
        "final_score": 1000 - i,
        "round_scores": json.dumps([100, 100, 100, 100, 100 - i]),
    }


def alltime_row(i: int) -> dict:
    return {"username": f"player_{i:02d}", "best_score": 1000 - i, "avg_score": 800.0, "games_played": 100}


def assert_within_discord_limits(embed):
    assert all(len(f.value) <= 1024 for f in embed.fields)
    assert len(embed.fields) <= 25
    assert len(embed) <= DISCORD_EMBED_TOTAL_LIMIT


def test_daily_leaderboard_with_many_players_splits_fields():
    embed = embeds.daily_leaderboard_embed("2026-11-15", [score_row(i) for i in range(40)])
    assert_within_discord_limits(embed)
    assert len(embed.fields) > 1
    rendered = "\n".join(f.value for f in embed.fields)
    assert "PlayerWithAVeryLongName39" in rendered


def test_all_time_leaderboard_is_capped():
    embed = embeds.all_time_leaderboard_embed([alltime_row(i) for i in range(60)])
    assert_within_discord_limits(embed)
    rendered = "\n".join(f.value for f in embed.fields)
    assert "player_14" in rendered
    assert "player_15" not in rendered
    assert "and 45 more" in rendered


def test_weekly_and_monthly_with_many_players():
    weekly = [{"username": f"p{i}", "weekly_score": 4000, "weekly_avg": 800.0, "best_score": 900, "games_played": 7}
              for i in range(60)]
    monthly = [{"username": f"p{i}", "monthly_score": 18000, "monthly_avg": 800.0, "best_score": 900, "games_played": 30}
               for i in range(60)]
    assert_within_discord_limits(embeds.weekly_leaderboard_embed(2026, 46, weekly))
    assert_within_discord_limits(embeds.monthly_leaderboard_embed(2026, 11, monthly))
