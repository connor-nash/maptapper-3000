import discord
from discord import app_commands
from discord.ext import commands

import database as db
import embeds


class AchievementsCmd(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="achievements", description="View your MapTap achievements")
    async def achievements(self, interaction: discord.Interaction):
        await interaction.response.defer()
        player = await db.get_player_by_discord_id(str(interaction.user.id))
        if player is None:
            await interaction.followup.send("No achievements yet — go play!", ephemeral=True)
            return

        ach_rows = await db.get_player_achievements(player["id"])
        embed = embeds.achievements_embed(interaction.user.display_name, ach_rows)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AchievementsCmd(bot))
