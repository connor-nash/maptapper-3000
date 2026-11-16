"""
Scheduled summary posts.
- 7 AM MT daily: daily leaderboard + daily achievements
- 7 AM MT Monday: also weekly leaderboard + weekly achievements
- 7 AM MT 1st of month: also monthly leaderboard + monthly achievements
"""

import json
import logging
from datetime import datetime, date, timedelta
import discord
from discord.ext import commands, tasks

import database as db
import achievements as ach
import embeds
from config import TIMEZONE, SUMMARY_HOUR, SUMMARY_MINUTE, mt_today

log = logging.getLogger(__name__)

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
        if (now.hour, now.minute) < (SUMMARY_HOUR, SUMMARY_MINUTE):
            return
        await self._post_pending_summaries()

    @check_summaries.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()
        try:
            await self._post_pending_summaries()
            await self._check_shakeup_catchup()
        except Exception:
            log.exception("Startup catch-up failed")

    @check_summaries.error
    async def on_loop_error(self, error: Exception):
        log.exception("Scheduler loop crashed; restarting", exc_info=error)
        self.check_summaries.restart()

    async def _post_pending_summaries(self):
        channel_id = await db.get_config("score_channel_id")
        if not channel_id:
            return
        channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            return

        today = mt_today()
        yesterday = today - timedelta(days=1)
        await self._post_once("daily", yesterday.isoformat(),
                              lambda: self._post_daily_summary(channel, yesterday))

        # Always target the most recently completed week/month so a missed Monday or 1st still posts.
        last_week = today - timedelta(days=today.weekday() + 7)
        iso_year, iso_week, _ = last_week.isocalendar()
        weekly_posted = await self._post_once("weekly", f"{iso_year}-W{iso_week:02d}",
                                              lambda: self._post_weekly_summary(channel, iso_year, iso_week))
        if weekly_posted:
            await self._run_safely("Bungus crowning",
                                   lambda: self._crown_bungus_jones(channel.guild, iso_year, iso_week))

        last_month = today.replace(day=1) - timedelta(days=1)
        await self._post_once("monthly", f"{last_month.year:04d}-{last_month.month:02d}",
                              lambda: self._post_monthly_summary(channel, last_month.year, last_month.month))

    async def _post_once(self, summary_type: str, period: str, post) -> bool:
        if await db.is_summary_posted(summary_type, period):
            return False
        if not await self._run_safely(f"{summary_type} summary for {period}", post):
            return False
        await db.mark_summary_posted(summary_type, period)
        return True

    async def _run_safely(self, label: str, action) -> bool:
        # One failed post (Discord outage, bad embed) must not take down the other summaries or the loop.
        try:
            await action()
            return True
        except Exception:
            log.exception("%s failed", label)
            return False

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
        bungus = await db.get_weekly_bungus(iso_year, iso_week)
        week_scores = await db.get_scores_for_week(iso_year, iso_week)

        embed = embeds.weekly_leaderboard_embed(iso_year, iso_week, weekly_data, bungus, week_scores)

        weekly_achievements = await ach.check_weekly_achievements(iso_year, iso_week)
        for name, value in embeds.weekly_achievements_fields(weekly_achievements):
            embed.add_field(name=name, value=value, inline=False)

        await channel.send(embed=embed)

    async def _crown_bungus_jones(self, guild: discord.Guild, iso_year: int, iso_week: int):
        bungus = await db.get_weekly_bungus(iso_year, iso_week)
        prev_id = await db.get_config("current_bungus_id")
        new_id = bungus["discord_id"] if bungus else ""

        # Update current_bungus_id BEFORE clearing the previous member's nick so
        # on_member_update doesn't mistake the un-Bungusing for an escape attempt.
        await db.set_config("current_bungus_id", new_id)

        if prev_id and prev_id != new_id:
            prev_member = guild.get_member(int(prev_id))
            if prev_member:
                try:
                    await prev_member.edit(nick=None)
                except (discord.Forbidden, discord.HTTPException):
                    pass

        if not new_id:
            return

        new_member = guild.get_member(int(new_id))
        if new_member:
            try:
                await new_member.edit(nick="Bungus Jones")
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def _post_monthly_summary(self, channel: discord.TextChannel, year: int, month: int):
        monthly_data = await db.compute_monthly_scores(year, month)
        month_scores = await db.get_scores_for_month(year, month)
        embed = embeds.monthly_leaderboard_embed(year, month, monthly_data, month_scores)

        monthly_achievements = await ach.check_monthly_achievements(year, month)
        for name, value in embeds.monthly_achievements_fields(monthly_achievements):
            embed.add_field(name=name, value=value, inline=False)

        await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Scheduler(bot))
