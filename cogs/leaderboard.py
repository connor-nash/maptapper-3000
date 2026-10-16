import discord
from discord import app_commands
from discord.ext import commands

import database as db
import embeds
from config import HANDICAP_WINDOW_DAYS, MIN_HANDICAP_GAMES, mt_today


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show the MapTap leaderboard")
    @app_commands.describe(view="Which leaderboard to show")
    @app_commands.choices(view=[
        app_commands.Choice(name="All Time", value="alltime"),
        app_commands.Choice(name="Today", value="daily"),
        app_commands.Choice(name="This Week", value="weekly"),
        app_commands.Choice(name="This Month", value="monthly"),
        app_commands.Choice(name="♿ Handicap", value="handicap"),
    ])
    async def leaderboard(self, interaction: discord.Interaction, view: str = "alltime"):
        await interaction.response.defer()

        now = mt_today()

        if view == "daily":
            scores = await db.get_scores_for_date(now.isoformat())
            embed = embeds.daily_leaderboard_embed(now.isoformat(), scores)

        elif view == "weekly":
            iso_year, iso_week, _ = now.isocalendar()
            weekly_data = await db.compute_weekly_scores(iso_year, iso_week)
            embed = embeds.weekly_leaderboard_embed(iso_year, iso_week, weekly_data)

        elif view == "monthly":
            monthly_data = await db.compute_monthly_scores(now.year, now.month)
            embed = embeds.monthly_leaderboard_embed(now.year, now.month, monthly_data)

        elif view == "alltime":
            rows = await db.get_all_time_leaderboard()
            embed = embeds.all_time_leaderboard_embed(rows)

        elif view == "handicap":
            embed = await self._build_handicap_embed()

        await interaction.followup.send(embed=embed)

    async def _build_handicap_embed(self) -> discord.Embed:
        all_players = await db.get_all_players()
        avgs = []
        for p in all_players:
            games = await db.get_player_game_count(p["id"])
            if games < MIN_HANDICAP_GAMES:
                continue
            rolling = await db.get_player_rolling_avg(p["id"], HANDICAP_WINDOW_DAYS)
            if rolling is not None:
                avgs.append((p, rolling))

        if not avgs:
            return embeds.handicap_leaderboard_embed([])

        group_avg = sum(a for _, a in avgs) / len(avgs)

        entries = []
        for p, personal_avg in avgs:
            # Need today's score for the adjusted leaderboard
            today_score = await db.get_score(p["id"], mt_today().isoformat())
            if today_score is None:
                continue
            raw = today_score["final_score"]
            adjusted = raw + (group_avg - personal_avg)
            entries.append({
                "username": p["username"],
                "raw": raw,
                "adjusted": adjusted,
            })

        entries.sort(key=lambda x: x["adjusted"], reverse=True)
        return embeds.handicap_leaderboard_embed(entries)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))
