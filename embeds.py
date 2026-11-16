"""
Discord embed builders for MapTapper 3000.
All leaderboards and summaries are built here.
"""

import json
from datetime import date
import discord
from discord.utils import escape_markdown
from config import EMBED_COLOR, MAPTAP_URL
from database import _iso_week_date_range, compute_daily_highlights, compute_period_highlights


MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}

FIELD_VALUE_LIMIT = 1024
ALL_TIME_ROW_LIMIT = 15


def _medal(rank: int) -> str:
    return MEDAL.get(rank, f"**{rank}.**")


def _add_list_field(embed: discord.Embed, name: str, lines: list[str]):
    # Discord rejects field values over 1024 chars, so long lists spill into unnamed continuation fields.
    chunk: list[str] = []
    for line in lines:
        if chunk and len("\n".join(chunk + [line])) > FIELD_VALUE_LIMIT:
            embed.add_field(name=name, value="\n".join(chunk), inline=False)
            name, chunk = "\u200b", []
        chunk.append(line[:FIELD_VALUE_LIMIT])
    if chunk:
        embed.add_field(name=name, value="\n".join(chunk), inline=False)


def _all_time_lines(rows: list) -> list[str]:
    lines = [
        f"{_medal(i)} **{row['username']}** — {row['best_score']} best"
        f"  |  {row['avg_score']:.0f} avg  |  {row['games_played']} games"
        for i, row in enumerate(rows[:ALL_TIME_ROW_LIMIT], 1)
    ]
    if len(rows) > ALL_TIME_ROW_LIMIT:
        lines.append(f"*…and {len(rows) - ALL_TIME_ROW_LIMIT} more*")
    return lines


def daily_leaderboard_embed(game_date: str, scores: list) -> discord.Embed:
    day = date.fromisoformat(game_date)
    embed = discord.Embed(
        title=f"📍 MapTap Daily — {day.strftime('%A, %b %-d')}",
        color=EMBED_COLOR,
        url=MAPTAP_URL,
    )

    if not scores:
        embed.description = f"Play today's game at [maptap.gg]({MAPTAP_URL})"
        embed.add_field(name="No scores posted yet", value="Be the first!", inline=False)
        return embed

    lines = []
    for i, row in enumerate(scores, 1):
        rounds = " · ".join(str(r) for r in json.loads(row["round_scores"]))
        lines.append(f"{MEDAL.get(i, f'{i}.')} {escape_markdown(row['username'])} — **{row['final_score']}**  ·  {rounds}")
    _add_list_field(embed, "Leaderboard", lines)

    h = compute_daily_highlights(scores)
    numbers = [
        f"Group avg **{h['group_avg']:.0f}** · {h['player_count']} players · "
        f"Hardest round: R{h['hardest_round']} (avg {h['hardest_round_avg']:.0f})"
    ]
    if h["shot"]:
        s = h["shot"]
        numbers.append(
            f"🎯 Shot of the day: **{escape_markdown(s['username'])}** — {s['score']} on R{s['round']}, "
            f"group avg {s['group_avg']:.0f} (+{s['value']:.0f})"
        )
    if h["whiff"]:
        w = h["whiff"]
        numbers.append(
            f"🫠 Whiff of the day: **{escape_markdown(w['username'])}** — {w['score']} on R{w['round']} "
            f"(−{w['cost']} pts)"
        )
    embed.add_field(name="📊 The Day in Numbers", value="\n".join(numbers), inline=False)
    return embed


def weekly_leaderboard_embed(
    iso_year: int,
    iso_week: int,
    weekly_data: list,
    bungus: dict | None = None,
    week_scores: list | None = None,
) -> discord.Embed:
    start_str, end_str = _iso_week_date_range(iso_year, iso_week)
    start_d, end_d = date.fromisoformat(start_str), date.fromisoformat(end_str)
    embed = discord.Embed(
        title=f"📅 Weekly Recap — {start_d.strftime('%b %-d')} – {end_d.strftime('%b %-d')} (Week {iso_week})",
        color=EMBED_COLOR,
        url=MAPTAP_URL,
    )
    embed.description = (
        "Drop 2 lowest scores (including missed days), average the remaining 5.\n"
        f"Play at [maptap.gg]({MAPTAP_URL})"
    )

    active = [d for d in weekly_data if d["weekly_score"] > 0]
    if not active:
        embed.add_field(name="No scores this week", value="​", inline=False)
        return embed

    by_avg = sorted(active, key=lambda x: x["weekly_avg"], reverse=True)
    avg_lines = [
        f"{MEDAL.get(i, f'{i}.')} {escape_markdown(d['username'])} — **{d['weekly_avg']:.1f}**"
        f"  ·  {d['best_score']} best  ·  {d['games_played']}/7 days"
        for i, d in enumerate(by_avg, 1)
    ]
    _add_list_field(embed, "🏅 Standings (Drop-2 Average)", avg_lines)

    h = compute_period_highlights(week_scores or [])
    if h:
        hd = date.fromisoformat(h["hardest_day"]["game_date"])
        hg = h["high_game"]
        hg_d = date.fromisoformat(hg["game_date"])
        numbers = [
            f"Group avg **{h['group_avg']:.0f}** · {h['total_games']} games played · "
            f"Hardest day: {hd.strftime('%a, %b %-d')} (avg {h['hardest_day']['avg']:.0f})",
            f"⚡ High game of the week: **{escape_markdown(hg['username'])}** — **{hg['score']}** ({hg_d.strftime('%a, %b %-d')})",
        ]
        if h["shot"]:
            s = h["shot"]
            sd = date.fromisoformat(s["game_date"])
            numbers.append(
                f"🎯 Shot of the week: **{escape_markdown(s['username'])}** — {s['score']} on R{s['round']}, "
                f"group avg {s['group_avg']:.0f} (+{s['value']:.0f}, {sd.strftime('%a')})"
            )
        if h["whiff"]:
            w = h["whiff"]
            wd = date.fromisoformat(w["game_date"])
            numbers.append(
                f"🫠 Whiff of the week: **{escape_markdown(w['username'])}** — {w['score']} on R{w['round']} "
                f"(−{w['cost']} pts, {wd.strftime('%a')})"
            )
        embed.add_field(name="📊 The Week in Numbers", value="\n".join(numbers), inline=False)

    if bungus:
        game_date = date.fromisoformat(bungus["game_date"])
        embed.add_field(
            name="💩 Bungus Jones",
            value=f"**{escape_markdown(bungus['username'])}** — **{bungus['worst_score']}** ({game_date.strftime('%a, %b %-d')})",
            inline=False,
        )

    return embed


def monthly_leaderboard_embed(year: int, month: int, monthly_data: list) -> discord.Embed:
    from calendar import month_name, monthrange
    days_in_month = monthrange(year, month)[1]
    embed = discord.Embed(
        title=f"🗓️ Monthly Recap — {month_name[month]} {year}",
        color=EMBED_COLOR,
        url=MAPTAP_URL,
    )
    embed.description = (
        "Drop 8 lowest scores (including missed days), average the remaining.\n"
        f"Play at [maptap.gg]({MAPTAP_URL})"
    )

    if not monthly_data:
        embed.add_field(name="No scores this month", value="​", inline=False)
        return embed

    # Average (of kept scores) — primary ranking
    by_avg = sorted(monthly_data, key=lambda x: x["monthly_avg"], reverse=True)
    avg_lines = [
        f"{_medal(i)} **{d['username']}** — {d['monthly_avg']:.1f} *({d['games_played']}/{days_in_month} days)*"
        for i, d in enumerate(by_avg, 1)
    ]
    _add_list_field(embed, "🏅 Average Score (Drop-8)", avg_lines)

    embed.add_field(name="​", value="​", inline=False)

    # Best single score
    by_best = sorted(monthly_data, key=lambda x: x["best_score"], reverse=True)
    best_lines = [
        f"{_medal(i)} **{d['username']}** — {d['best_score']}"
        for i, d in enumerate(by_best, 1)
    ]
    _add_list_field(embed, "⚡ Best Single Score", best_lines)

    return embed


def all_time_leaderboard_embed(rows: list) -> discord.Embed:
    embed = discord.Embed(
        title="🌍 All-Time Leaderboard",
        description="Ranked by best single score.",
        color=EMBED_COLOR,
        url=MAPTAP_URL,
    )

    if not rows:
        embed.add_field(name="No scores yet", value="​", inline=False)
        return embed

    _add_list_field(embed, "Rankings", _all_time_lines(rows))
    return embed


def shakeup_embed(mover_name: str, old_top3: list, new_top3: list, all_rows: list) -> discord.Embed:
    old_names = [n for n, _ in old_top3]
    new_names = [n for n, _ in new_top3]

    new_rank = new_names.index(mover_name) + 1 if mover_name in new_names else 1
    was_in_top3 = mover_name in old_names

    if new_rank == 1:
        verb = "moves to #1"
    elif was_in_top3:
        verb = f"moves up to #{new_rank}"
    else:
        verb = f"crashes into the top 3 at #{new_rank}"

    bumped_off = [n for n in old_names if n not in new_names]
    dropped_within = [n for n in new_names
                      if n in old_names and n != mover_name
                      and new_names.index(n) > old_names.index(n)]

    if new_rank == 1 and old_names and old_names[0] != mover_name:
        suffix = f" **{old_names[0]}** has been dethroned."
    elif bumped_off:
        suffix = f" **{bumped_off[0]}** has been removed from the podium."
    elif dropped_within:
        suffix = f" **{dropped_within[0]}** has been reminded of their place."
    else:
        suffix = ""

    message = f"🥊 **{mover_name}** {verb} all time.{suffix}"

    embed = discord.Embed(
        title="🌍 All-Time Leaderboard",
        description=message,
        color=EMBED_COLOR,
        url=MAPTAP_URL,
    )
    _add_list_field(embed, "Ranked by best single score", _all_time_lines(all_rows))
    return embed


def shame_board_embed(mover_name: str, old_bottom3: list, new_bottom3: list, bottom_rows: list) -> discord.Embed:
    old_names = [n for n, _ in old_bottom3]
    new_names = [n for n, _ in new_bottom3]

    new_rank = new_names.index(mover_name) + 1 if mover_name in new_names else None
    was_in_bottom3 = mover_name in old_names

    if new_rank == 1:
        if was_in_bottom3:
            message = f"💀 **{mover_name}** somehow found a new low. Incredible."
        else:
            message = f"💀 **{mover_name}** has claimed the worst score in recorded history."
    elif new_rank:
        if was_in_bottom3:
            message = f"💀 **{mover_name}** digs deeper into the shame board at #{new_rank}."
        else:
            message = f"💀 **{mover_name}** crashes into the shame board at #{new_rank}."
    else:
        message = f"💀 **{mover_name}** has shaken up the shame board."

    bumped_off = [n for n in old_names if n not in new_names]
    if bumped_off:
        message += f" **{bumped_off[0]}** has been mercifully removed from the dishonor roll."

    lines = []
    for i, row in enumerate(bottom_rows, 1):
        lines.append(
            f"💀 **{row['username']}** — {row['worst_score']} worst"
            f"  |  {row['avg_score']:.0f} avg  |  {row['games_played']} games"
        )

    embed = discord.Embed(
        title="🗑️ All-Time Shame Board",
        description=message,
        color=0xE74C3C,
        url=MAPTAP_URL,
    )
    _add_list_field(embed, "Personal worst scores", lines)
    return embed


def handicap_leaderboard_embed(entries: list) -> discord.Embed:
    embed = discord.Embed(
        title="♿ Handicap Leaderboard",
        description="Adjusted score = your score + (group avg − your 30-day avg). Levels the playing field.",
        color=EMBED_COLOR,
    )

    if not entries:
        embed.add_field(name="Not enough data yet", value="Need at least a few days of scores.", inline=False)
        return embed

    lines = []
    for i, e in enumerate(entries, 1):
        delta = e["adjusted"] - e["raw"]
        delta_str = f"+{delta:.0f}" if delta >= 0 else f"{delta:.0f}"
        lines.append(
            f"{_medal(i)} **{e['username']}** — {e['adjusted']:.0f} adj "
            f"*(raw {e['raw']}, handicap {delta_str})*"
        )

    _add_list_field(embed, "Rankings", lines)
    return embed


def player_stats_embed(username: str, stats: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"📊 Stats — {username}",
        color=EMBED_COLOR,
    )
    embed.add_field(name="Games Played", value=str(stats.get("games_played", 0)), inline=True)
    embed.add_field(name="All-Time Total", value=f"{stats.get('total_score', 0):,}", inline=True)
    embed.add_field(name="Personal Best", value=str(stats.get("best_score", "—")), inline=True)
    embed.add_field(name="All-Time Avg", value=f"{stats.get('avg_score', 0):.1f}", inline=True)
    embed.add_field(name="30-Day Avg", value=f"{stats.get('rolling_avg', 0):.1f}", inline=True)
    embed.add_field(name="Current Streak", value=f"{stats.get('streak', 0)} days", inline=True)
    embed.add_field(name="🦃 Turkeys", value=str(stats.get("turkeys", 0)), inline=True)
    embed.add_field(name="🎯 Perfect Scores", value=str(stats.get("perfect_scores", 0)), inline=True)
    embed.add_field(name="💯 Perfect Rounds", value=str(stats.get("perfect_rounds", 0)), inline=True)
    embed.add_field(name="🫗 Fumbles", value=str(stats.get("fumbles", 0)), inline=True)
    embed.add_field(name="🇰🇿 Nice", value=str(stats.get("nice_count", 0)), inline=True)
    return embed


def achievements_embed(username: str, achievements: list) -> discord.Embed:
    embed = discord.Embed(
        title=f"🏆 Achievements — {username}",
        color=EMBED_COLOR,
    )

    ACHIEVEMENT_LABELS = {
        "perfect_score": "🎯 Perfect Score (1000)",
        "turkey": "🦃 The Turkey (3× 100 in one game)",
        "fumble": "🏈 Fumble",
        "twinsies": "👯 Twinsies",
        "lost_bud": "🗺️ I Think Yer Fuckin' Lost Bud",
        "most_improved": "📈 Most Improved",
        "get_a_life": "🤪 Get a Life",
        "mia": "🫧 MIA",
        "sixty_nine": "🇰🇿 Very Nice (69)",
    }

    if not achievements:
        embed.description = "No achievements yet. Get out there and play!"
        return embed

    # Group by type
    by_type: dict[str, list] = {}
    for a in achievements:
        t = a["achievement_type"]
        # Normalize milestone types
        if t.startswith("score_milestone_"):
            t = "score_milestone"
        elif t.startswith("perfect_round_milestone_"):
            t = "perfect_round_milestone"
        by_type.setdefault(t, []).append(a)

    lines = []
    for achievement_type, entries in by_type.items():
        label = ACHIEVEMENT_LABELS.get(achievement_type)
        if not label:
            if achievement_type == "score_milestone":
                label = "🏆 Score Milestone"
            elif achievement_type == "perfect_round_milestone":
                label = "💯 Perfect Round Milestone"
            else:
                label = achievement_type.replace("_", " ").title()
        lines.append(f"**{label}** × {len(entries)}")

    embed.description = "\n".join(lines)
    return embed


def daily_achievements_field(achievements: list) -> list[tuple[str, str]]:
    """Returns list of (name, value) field tuples for daily achievements."""
    fields = []
    for a in achievements:
        t = a["type"]
        m = a.get("metadata", {})
        if t == "twinsies":
            players_str = " & ".join(f"**{n}**" for n in a["players"])
            fields.append((
                "👯 Twinsies",
                f"{players_str} both scored **{m['score']}**. Suspicious."
            ))
    return fields


def weekly_achievements_fields(achievements: list) -> list[tuple[str, str]]:
    fields = []
    for a in achievements:
        if a["type"] == "lost_bud":
            m = a["metadata"]
            fields.append((
                "🗺️ I Think Yer Fuckin' Lost Bud",
                f"**{a['username']}** scored **{m['score']}** on round {m['round']} "
                f"({m['date']}) — the worst single guess all week."
            ))
    return fields


def monthly_achievements_fields(achievements: list) -> list[tuple[str, str]]:
    fields = []
    get_a_life_names = []
    mia_entries = []

    for a in achievements:
        m = a.get("metadata", {})
        if a["type"] == "most_improved":
            fields.append((
                "📈 Most Improved",
                f"**{a['username']}** — avg went from {m['prev_avg']:.1f} → {m['curr_avg']:.1f} "
                f"(+{m['improvement']:.1f} pts)"
            ))
        elif a["type"] == "get_a_life":
            get_a_life_names.append(a["username"])
        elif a["type"] == "mia":
            mia_entries.append((a["username"], m.get("games_played", "?")))

    if get_a_life_names:
        names_str = ", ".join(f"**{n}**" for n in get_a_life_names)
        fields.append((
            "🤪 Get a Life",
            f"{names_str} played every single day this month. Seek help."
        ))

    if mia_entries:
        mia_str = ", ".join(f"**{name}** ({games} games)" for name, games in mia_entries)
        fields.append(("🫧 MIA", mia_str))

    return fields


def immediate_achievement_embed(username: str, discord_id: str, achievement: dict) -> discord.Embed:
    t = achievement["type"]
    m = achievement.get("metadata", {})

    if t == "perfect_score":
        embed = discord.Embed(
            title="🎯 PERFECT SCORE",
            description=f"**{username}** just scored 1000. An absolute moment.",
            color=0xFFD700,
        )
    elif t == "turkey":
        embed = discord.Embed(
            title="🦃 THE TURKEY",
            description=f"**{username}** hit {m['perfect_rounds']} perfect 100s in one game. Gobble gobble.",
            color=EMBED_COLOR,
        )
    elif t == "score_milestone":
        milestone = m["milestone"]
        total = m["total"]
        embed = discord.Embed(
            title=f"🏆 {milestone:,} POINTS",
            description=f"**{username}** has crossed **{milestone:,}** cumulative points ({total:,} total). Legend.",
            color=0xFFD700,
        )
    elif t == "perfect_round_milestone":
        milestone = m["milestone"]
        embed = discord.Embed(
            title=f"💯 {milestone} PERFECT ROUNDS",
            description=f"**{username}** has now scored a perfect 100 on **{milestone}** individual rounds.",
            color=EMBED_COLOR,
        )
    elif t == "fumble":
        embed = discord.Embed(
            title="🏈 FUMBLE",
            description=f"**{username}** fumbled it. Round {m['worst_round']} score of **{m['worst_score']}** "
                        f"tanked what should have been a {m['projected']}. Got {m['actual']} instead.",
            color=0xE67E22,
        )
    elif t == "sixty_nine":
        rounds = m.get("rounds", [])
        if len(rounds) == 1:
            round_str = f"round {rounds[0]}"
        else:
            round_str = ", ".join(f"round {r}" for r in rounds[:-1]) + f" and round {rounds[-1]}"
        embed = discord.Embed(
            title="🇰🇿 VERY NICE!! I LIKE THIS!",
            description=f"**{username}** scored a 69 on {round_str}.",
            color=EMBED_COLOR,
        )
    elif t == "deja_vu":
        score = m["score"]
        embed = discord.Embed(
            title="🔁 DÉJÀ VU",
            description=f"**{username}** scored {score}. Again. Exactly {score}. Are you okay?",
            color=EMBED_COLOR,
        )
    else:
        embed = discord.Embed(title="Achievement Unlocked", description=f"**{username}**: {t}", color=EMBED_COLOR)

    return embed
