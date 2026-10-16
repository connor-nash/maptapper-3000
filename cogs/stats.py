import json
from datetime import date, timedelta
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import embeds
from config import mt_today


async def _build_player_stats(player_id: int) -> dict:
    all_scores = await db.get_player_all_scores(player_id)
    if not all_scores:
        return {
            "games_played": 0, "total_score": 0, "best_score": None,
            "avg_score": 0.0, "rolling_avg": 0.0, "streak": 0,
            "turkeys": 0, "perfect_scores": 0, "perfect_rounds": 0, "fumbles": 0,
        }

    final_scores = [r["final_score"] for r in all_scores]
    games_played = len(all_scores)
    total_score = sum(final_scores)
    best_score = max(final_scores)
    avg_score = total_score / games_played

    rolling_avg = await db.get_player_rolling_avg(player_id, 30) or 0.0

    # Current streak: consecutive days ending today (or yesterday)
    played_dates = sorted({r["game_date"] for r in all_scores}, reverse=True)
    streak = 0
    check = mt_today()
    for d in played_dates:
        if d == check.isoformat() or d == (check - timedelta(days=1)).isoformat():
            streak += 1
            check = date.fromisoformat(d) - timedelta(days=1)
        else:
            break

    # Turkey count (from achievements)
    ach_rows = await db.get_player_achievements(player_id)
    turkeys = sum(1 for a in ach_rows if a["achievement_type"] == "turkey")
    perfect_scores = sum(1 for a in ach_rows if a["achievement_type"] == "perfect_score")
    fumbles = await db.get_player_fumble_count(player_id)
    perfect_rounds = await db.get_player_perfect_rounds_count(player_id)

    return {
        "games_played": games_played,
        "total_score": total_score,
        "best_score": best_score,
        "avg_score": avg_score,
        "rolling_avg": rolling_avg,
        "streak": streak,
        "turkeys": turkeys,
        "perfect_scores": perfect_scores,
        "perfect_rounds": perfect_rounds,
        "fumbles": fumbles,
    }


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="mystats", description="Show your personal MapTap stats")
    async def mystats(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        player = await db.get_player_by_discord_id(str(interaction.user.id))
        if player is None:
            await interaction.followup.send("No scores on record for you yet. Go play! " +
                                            f"<{embeds.MAPTAP_URL}>", ephemeral=True)
            return

        stats = await _build_player_stats(player["id"])
        embed = embeds.player_stats_embed(interaction.user.display_name, stats)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stats", description="Show another player's MapTap stats")
    @app_commands.describe(user="The player to look up")
    async def stats(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()
        player = await db.get_player_by_discord_id(str(user.id))
        if player is None:
            await interaction.followup.send(f"No scores on record for {user.display_name}.", ephemeral=True)
            return

        stats = await _build_player_stats(player["id"])
        embed = embeds.player_stats_embed(user.display_name, stats)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
