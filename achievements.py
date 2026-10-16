"""
Achievement detection logic.

Immediate achievements (returned from check_immediate_achievements):
  - perfect_score: final_score == 1000
  - turkey: three or more round scores of 100
  - score_milestone: cumulative score crossed a threshold
  - perfect_round_milestone: cumulative perfect rounds crossed a threshold

Daily achievements (returned from check_daily_achievements for a given date):
  - fumble: single bad round killed a projected 960+ game
  - twinsies: exact same final score as another player

Weekly achievements (returned from check_weekly_achievements):
  - lost_bud: worst individual round of the week

Monthly achievements (returned from check_monthly_achievements):
  - most_improved: biggest avg score improvement vs. prior month
  - get_a_life: played every day of the calendar month
  - mia: fewest games played that month
"""

import json
from typing import Optional
from config import (
    ROUND_WEIGHTS, FUMBLE_PROJECTED_THRESHOLD,
    SCORE_MILESTONES, PERFECT_ROUND_MILESTONES,
)
import database as db


def _projected_score_without_worst(round_scores: list[int]) -> tuple[int, int]:
    """
    Returns (projected_score, worst_round_index) if the worst round is replaced
    with the average of the other 4 rounds.
    """
    worst_idx = round_scores.index(min(round_scores))
    others = [round_scores[i] for i in range(5) if i != worst_idx]
    avg_others = sum(others) / len(others)

    projected = 0
    for i, (score, weight) in enumerate(zip(round_scores, ROUND_WEIGHTS)):
        if i == worst_idx:
            projected += avg_others * weight
        else:
            projected += score * weight
    return int(projected), worst_idx


async def check_immediate_achievements(
    player_id: int,
    round_scores: list[int],
    final_score: int,
    game_date: str,
) -> list[dict]:
    """
    Check achievements that announce immediately when a score is posted.
    Returns list of achievement dicts with keys: type, metadata.
    """
    results = []

    # Perfect score
    if final_score == 1000:
        already = await db.has_achievement(player_id, "perfect_score", game_date)
        if not already:
            await db.record_achievement(player_id, "perfect_score", game_date)
            results.append({"type": "perfect_score", "metadata": {}})

    # Turkey: 3+ perfect individual rounds
    perfect_count = sum(1 for r in round_scores if r == 100)
    if perfect_count >= 3:
        already = await db.has_achievement(player_id, "turkey", game_date)
        if not already:
            await db.record_achievement(player_id, "turkey", game_date, {"perfect_rounds": perfect_count})
            results.append({"type": "turkey", "metadata": {"perfect_rounds": perfect_count}})

    # Cumulative score milestones
    cumulative = await db.get_player_cumulative_score(player_id)
    prev_cumulative = cumulative - final_score
    for milestone in SCORE_MILESTONES:
        if prev_cumulative < milestone <= cumulative:
            already = await db.has_achievement(player_id, f"score_milestone_{milestone}", game_date)
            if not already:
                await db.record_achievement(player_id, f"score_milestone_{milestone}", game_date, {"milestone": milestone})
                results.append({"type": "score_milestone", "metadata": {"milestone": milestone, "total": cumulative}})

    # Very Nice: any round score of 69
    sixty_nine_rounds = [i + 1 for i, r in enumerate(round_scores) if r == 69]
    if sixty_nine_rounds:
        already = await db.has_achievement(player_id, "sixty_nine", game_date)
        if not already:
            await db.record_achievement(player_id, "sixty_nine", game_date, {"rounds": sixty_nine_rounds})
            results.append({"type": "sixty_nine", "metadata": {"rounds": sixty_nine_rounds}})

    # Perfect round milestones
    total_perfect = await db.get_player_perfect_rounds_count(player_id)
    prev_perfect = total_perfect - sum(1 for r in round_scores if r == 100)
    for milestone in PERFECT_ROUND_MILESTONES:
        if prev_perfect < milestone <= total_perfect:
            already = await db.has_achievement(player_id, f"perfect_round_milestone_{milestone}", game_date)
            if not already:
                await db.record_achievement(player_id, f"perfect_round_milestone_{milestone}", game_date, {"milestone": milestone})
                results.append({"type": "perfect_round_milestone", "metadata": {"milestone": milestone, "total": total_perfect}})

    return results


async def check_daily_achievements(game_date: str) -> list[dict]:
    """
    Check achievements for a completed day. Returns list of achievement dicts
    with keys: type, player_id, username, discord_id, metadata.
    """
    results = []
    scores = await db.get_scores_for_date(game_date)
    if not scores:
        return results

    # Fumble: a single bad round killed a projected 960+ game
    for row in scores:
        round_scores = json.loads(row["round_scores"])
        projected, worst_idx = _projected_score_without_worst(round_scores)
        worst_score = round_scores[worst_idx]
        avg_others = (sum(round_scores) - worst_score) / 4
        # It's a fumble if: projected >= threshold AND the bad round is at least 40 below avg
        if projected >= FUMBLE_PROJECTED_THRESHOLD and (avg_others - worst_score) >= 40:
            already = await db.has_achievement(row["player_id"], "fumble", game_date)
            if not already:
                await db.record_achievement(
                    row["player_id"], "fumble", game_date,
                    {"projected": projected, "actual": row["final_score"],
                     "worst_round": worst_idx + 1, "worst_score": worst_score}
                )
                results.append({
                    "type": "fumble",
                    "player_id": row["player_id"],
                    "username": row["username"],
                    "discord_id": row["discord_id"],
                    "metadata": {
                        "projected": projected,
                        "actual": row["final_score"],
                        "worst_round": worst_idx + 1,
                        "worst_score": worst_score,
                    }
                })

    # Twinsies: two or more players with exact same final score
    score_map: dict[int, list] = {}
    for row in scores:
        fs = row["final_score"]
        if fs not in score_map:
            score_map[fs] = []
        score_map[fs].append(row)

    for final_score, rows in score_map.items():
        if len(rows) >= 2:
            names = [r["username"] for r in rows]
            for row in rows:
                already = await db.has_achievement(row["player_id"], "twinsies", game_date)
                if not already:
                    others = [r["username"] for r in rows if r["player_id"] != row["player_id"]]
                    await db.record_achievement(
                        row["player_id"], "twinsies", game_date,
                        {"score": final_score, "shared_with": others}
                    )
            results.append({
                "type": "twinsies",
                "players": names,
                "metadata": {"score": final_score, "count": len(rows)}
            })

    return results


async def check_weekly_achievements(iso_year: int, iso_week: int) -> list[dict]:
    """Check weekly achievements. Returns list of achievement dicts."""
    results = []
    scores = await db.get_scores_for_week(iso_year, iso_week)
    if not scores:
        return results

    period = f"{iso_year}-W{iso_week:02d}"

    # I Think Yer Fuckin' Lost Bud: worst individual round of the week
    worst_score = 101
    worst_row = None
    worst_round_idx = None
    for row in scores:
        rounds = json.loads(row["round_scores"])
        for i, r in enumerate(rounds):
            if r < worst_score:
                worst_score = r
                worst_row = row
                worst_round_idx = i + 1

    if worst_row is not None:
        already = await db.has_achievement(worst_row["player_id"], "lost_bud", period)
        if not already:
            await db.record_achievement(
                worst_row["player_id"], "lost_bud", period,
                {"score": worst_score, "round": worst_round_idx, "date": worst_row["game_date"]}
            )
            results.append({
                "type": "lost_bud",
                "player_id": worst_row["player_id"],
                "username": worst_row["username"],
                "discord_id": worst_row["discord_id"],
                "metadata": {
                    "score": worst_score,
                    "round": worst_round_idx,
                    "date": worst_row["game_date"],
                }
            })

    return results


async def check_monthly_achievements(year: int, month: int) -> list[dict]:
    """Check monthly achievements. Returns list of achievement dicts."""
    import calendar
    results = []
    period = f"{year:04d}-{month:02d}"
    days_in_month = calendar.monthrange(year, month)[1]
    all_players = await db.get_all_players()

    if not all_players:
        return results

    # Get a Life / MIA: track games played per player
    player_game_counts = []
    for player in all_players:
        count = await db.get_player_month_game_count(player["id"], year, month)
        player_game_counts.append({
            "player_id": player["id"],
            "discord_id": player["discord_id"],
            "username": player["username"],
            "games_played": count,
        })

    # Get a Life: perfect attendance (every day of the month)
    perfect_players = [p for p in player_game_counts if p["games_played"] == days_in_month]
    for p in perfect_players:
        already = await db.has_achievement(p["player_id"], "get_a_life", period)
        if not already:
            await db.record_achievement(p["player_id"], "get_a_life", period, {"days": days_in_month})
        results.append({
            "type": "get_a_life",
            "player_id": p["player_id"],
            "username": p["username"],
            "discord_id": p["discord_id"],
            "metadata": {"days": days_in_month},
        })

    # MIA: fewest games played (among players who played at least once)
    active_players = [p for p in player_game_counts if p["games_played"] > 0]
    if active_players:
        min_games = min(p["games_played"] for p in active_players)
        mia_players = [p for p in active_players if p["games_played"] == min_games]
        for p in mia_players:
            already = await db.has_achievement(p["player_id"], "mia", period)
            if not already:
                await db.record_achievement(p["player_id"], "mia", period, {"games_played": min_games})
            results.append({
                "type": "mia",
                "player_id": p["player_id"],
                "username": p["username"],
                "discord_id": p["discord_id"],
                "metadata": {"games_played": min_games, "days_in_month": days_in_month},
            })

    # Most Improved: biggest increase in avg score vs. prior month
    improvements = []
    for player in all_players:
        curr_avg = await db.get_player_current_month_avg(player["id"], year, month)
        prev_avg = await db.get_player_prev_month_avg(player["id"], year, month)
        if curr_avg is not None and prev_avg is not None:
            improvements.append({
                "player_id": player["id"],
                "discord_id": player["discord_id"],
                "username": player["username"],
                "improvement": curr_avg - prev_avg,
                "curr_avg": curr_avg,
                "prev_avg": prev_avg,
            })

    if improvements:
        best = max(improvements, key=lambda x: x["improvement"])
        if best["improvement"] > 0:
            already = await db.has_achievement(best["player_id"], "most_improved", period)
            if not already:
                await db.record_achievement(
                    best["player_id"], "most_improved", period,
                    {"improvement": best["improvement"], "curr_avg": best["curr_avg"], "prev_avg": best["prev_avg"]}
                )
            results.append({
                "type": "most_improved",
                "player_id": best["player_id"],
                "username": best["username"],
                "discord_id": best["discord_id"],
                "metadata": best,
            })

    return results
