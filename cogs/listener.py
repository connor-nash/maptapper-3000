"""
Listens for MapTap score pastes in the configured channel.
On valid parse: stores score, checks immediate achievements, reacts ✅.
On invalid (looks like MapTap but can't parse): reacts ❌.
"""

import discord
from discord.ext import commands

import database as db
import achievements as ach
import embeds
from parser import parse_maptap_share, looks_like_maptap


class Listener(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        # Check if this is the configured score channel
        channel_id = await db.get_config("score_channel_id")
        if not channel_id or str(message.channel.id) != channel_id:
            return

        content = message.content
        if not looks_like_maptap(content):
            return

        parsed = parse_maptap_share(content)
        if parsed is None:
            await message.add_reaction("❌")
            return

        # Upsert player
        player_id = await db.upsert_player(
            str(message.author.id), message.author.display_name
        )

        # Capture all-time top 3 before insert for shakeup detection
        pre_rows = await db.get_all_time_leaderboard()
        old_top3 = [(r["username"], r["best_score"]) for r in pre_rows[:3]]

        # Insert score (first post wins)
        inserted = await db.insert_score(
            player_id, parsed.game_date, parsed.round_scores, parsed.final_score
        )

        if not inserted:
            # Already have a score for this player/date — silently ignore
            await message.add_reaction("✅")
            return

        await message.add_reaction("✅")

        # Check all-time top 3 shakeup
        post_rows = await db.get_all_time_leaderboard()
        new_top3 = [(r["username"], r["best_score"]) for r in post_rows[:3]]
        old_scores = [s for _, s in old_top3]
        new_scores = [s for _, s in new_top3]
        if old_scores != new_scores:
            mover = message.author.display_name
            embed = embeds.shakeup_embed(mover, old_top3, new_top3, post_rows)
            await message.channel.send(embed=embed)
            import json
            await db.set_config("last_top3", json.dumps(
                [{"username": n, "best_score": s} for n, s in new_top3]
            ))

        # Check immediate achievements
        immediate = await ach.check_immediate_achievements(
            player_id, parsed.round_scores, parsed.final_score, parsed.game_date
        )
        for achievement in immediate:
            embed = embeds.immediate_achievement_embed(
                message.author.display_name, str(message.author.id), achievement
            )
            await message.channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Listener(bot))
