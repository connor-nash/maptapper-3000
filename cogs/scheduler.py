"""
Scheduled summary posts.
- 7 AM MT daily: daily leaderboard + daily achievements
- 7 AM MT Monday: also weekly leaderboard + weekly achievements
- 7 AM MT 1st of month: also monthly leaderboard + monthly achievements
"""

import json
from datetime import datetime, date, timedelta
import pytz
import discord
from discord.ext import commands, tasks

import database as db
import achievements as ach
import embeds
from config import TIMEZONE, SUMMARY_HOUR, SUMMARY_MINUTE, MAPTAP_URL, mt_today

# Initial all-time top 3 before any real scores were posted
_INITIAL_TOP3 = [
    {"username": "pitystomper69", "best_score": 990},
    {"username": "chicken__man.", "best_score": 984},
    {"username": "Zach Coury",    "best_score": 969},
]


class Scheduler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_summaries.start()

    def cog_unload(self):
        self.check_summaries.cancel()

    @tasks.loop(minutes=1)
    async def check_summaries(self):
        now = datetime.now(TIMEZONE)
        if now.hour != SUMMARY_HOUR or now.minute != SUMMARY_MINUTE:
            return
        await self._post_pending_summaries()

    @check_summaries.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
        await self._post_pending_summaries()
        await self._check_shakeup_catchup()

    async def _post_pending_summaries(self):
        channel_id = await db.get_config("score_channel_id")
        if not channel_id:
            return
        channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            return

        yesterday = mt_today() - timedelta(days=1)
        today = mt_today()

        # Daily summary (for yesterday)
        daily_period = yesterday.isoformat()
        if not await db.is_summary_posted("daily", daily_period):
            await self._post_daily_summary(channel, yesterday)
            await db.mark_summary_posted("daily", daily_period)

        # Weekly summary: post on Monday for the previous week
        if today.weekday() == 0:
            prev_monday = today - timedelta(days=7)
            iso_year, iso_week, _ = prev_monday.isocalendar()
            weekly_period = f"{iso_year}-W{iso_week:02d}"
            if not await db.is_summary_posted("weekly", weekly_period):
                await self._post_weekly_summary(channel, iso_year, iso_week)
                await db.mark_summary_posted("weekly", weekly_period)

        # Monthly summary: post on 1st for previous month
        if today.day == 1:
            if today.month == 1:
                prev_year, prev_month = today.year - 1, 12
            else:
                prev_year, prev_month = today.year, today.month - 1
            monthly_period = f"{prev_year:04d}-{prev_month:02d}"
            if not await db.is_summary_posted("monthly", monthly_period):
                await self._post_monthly_summary(channel, prev_year, prev_month)
                await db.mark_summary_posted("monthly", monthly_period)

    async def _check_shakeup_catchup(self):
        """On startup, post a shakeup if the all-time top 3 changed since last announced."""
        channel_id = await db.get_config("score_channel_id")
        if not channel_id:
            return
        channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            return

        stored = await db.get_config("last_top3")
        last_top3 = json.loads(stored) if stored else _INITIAL_TOP3
        last_scores = [d["best_score"] for d in last_top3]

        current_rows = await db.get_all_time_leaderboard()
        current_top3 = [(r["username"], r["best_score"]) for r in current_rows[:3]]
        current_scores = [s for _, s in current_top3]

        if last_scores == current_scores:
            return

        # Find mover: whoever has a best_score not in the previous top 3
        old_scores = set(last_scores)
        mover = next(
            (name for name, score in current_top3 if score not in old_scores),
            current_top3[0][0] if current_top3 else None,
        )
        if mover is None:
            return

        old_top3_tuples = [(d["username"], d["best_score"]) for d in last_top3]
        shakeup = embeds.shakeup_embed(mover, old_top3_tuples, current_top3, current_rows)
        await channel.send(embed=shakeup)
        await db.set_config("last_top3", json.dumps([{"username": n, "best_score": s} for n, s in current_top3]))

    async def _post_daily_summary(self, channel: discord.TextChannel, for_date: date):
        scores = await db.get_scores_for_date(for_date.isoformat())
        embed = embeds.daily_leaderboard_embed(for_date.isoformat(), scores)

        daily_achievements = await ach.check_daily_achievements(for_date.isoformat())
        for name, value in embeds.daily_achievements_field(daily_achievements):
            embed.add_field(name=name, value=value, inline=False)

        await channel.send(embed=embed)

    async def _post_weekly_summary(self, channel: discord.TextChannel, iso_year: int, iso_week: int):
        weekly_data = await db.compute_weekly_scores(iso_year, iso_week)
        embed = embeds.weekly_leaderboard_embed(iso_year, iso_week, weekly_data)

        weekly_achievements = await ach.check_weekly_achievements(iso_year, iso_week)
        for name, value in embeds.weekly_achievements_fields(weekly_achievements):
            embed.add_field(name=name, value=value, inline=False)

        await channel.send(embed=embed)

    async def _post_monthly_summary(self, channel: discord.TextChannel, year: int, month: int):
        monthly_data = await db.compute_monthly_scores(year, month)
        embed = embeds.monthly_leaderboard_embed(year, month, monthly_data)

        monthly_achievements = await ach.check_monthly_achievements(year, month)
        for name, value in embeds.monthly_achievements_fields(monthly_achievements):
            embed.add_field(name=name, value=value, inline=False)

        await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Scheduler(bot))
