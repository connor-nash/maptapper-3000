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
        for cog in COGS:
            await self.load_extension(cog)
        await self.tree.sync()
        print(f"Synced slash commands.")

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
