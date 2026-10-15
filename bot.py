import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database as db

load_dotenv()
TOKEN = os.environ["DISCORD_TOKEN"]

COGS = [
    "cogs.listener",
    "cogs.leaderboard",
    "cogs.stats",
    "cogs.achievements_cmd",
    "cogs.admin",
    "cogs.scheduler",
]


class MapTapper(commands.Bot):
    async def setup_hook(self):
        await db.init_db()
        await self._seed_legacy_scores()
        for cog in COGS:
            await self.load_extension(cog)
        await self.tree.sync()
        print(f"Synced slash commands.")

    async def _seed_legacy_scores(self):
        """Seeds legacy scores on first boot if legacy scores don't exist yet."""
        if await db.has_legacy_scores():
            return
        legacy = [
            ("seed:pitystomper69", "pitystomper69", 990),
            ("seed:chicken__man.",  "chicken__man.",  984),
            ("seed:Zach Coury",     "Zach Coury",     969),
        ]
        for discord_id, username, final_score in legacy:
            await db.seed_score(discord_id, username, final_score)
        print("Seeded 3 legacy scores.")

    async def on_ready(self):
        print(f"MapTapper 3000 online as {self.user} ({self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="maptap.gg scores"
            )
        )


def main():
    intents = discord.Intents.default()
    intents.message_content = True

    bot = MapTapper(command_prefix="!", intents=intents)
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
