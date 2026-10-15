import discord
from discord import app_commands
from discord.ext import commands

import database as db


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    admin_group = app_commands.Group(name="admin", description="Admin-only bot management")

    @admin_group.command(name="set-channel", description="Set the channel where scores are posted")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await db.set_config("score_channel_id", str(channel.id))
        await interaction.response.send_message(
            f"✅ Score channel set to {channel.mention}. I'll watch for MapTap pastes there.",
            ephemeral=True,
        )

    @admin_group.command(name="reset", description="Reset ALL bot data (scores, achievements, config)")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction, confirm: str = ""):
        if confirm.lower() != "yes":
            await interaction.response.send_message(
                "⚠️ This will erase **all scores and achievements**. "
                "Run `/admin reset confirm:yes` to confirm.",
                ephemeral=True,
            )
            return

        import aiosqlite
        from database import DB_PATH
        async with aiosqlite.connect(DB_PATH) as db_conn:
            await db_conn.executescript("""
                DELETE FROM scores;
                DELETE FROM achievements;
                DELETE FROM summaries_posted;
                DELETE FROM players;
            """)
            await db_conn.commit()

        await interaction.response.send_message("💥 All data has been reset.", ephemeral=True)

    @admin_group.command(name="status", description="Show bot configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def status(self, interaction: discord.Interaction):
        channel_id = await db.get_config("score_channel_id")
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))
            channel_str = channel.mention if channel else f"<#{channel_id}> (not found)"
        else:
            channel_str = "Not configured — run `/admin set-channel`"

        await interaction.response.send_message(
            f"**MapTapper 3000 Status**\n"
            f"Score channel: {channel_str}",
            ephemeral=True,
        )

    @admin_group.command(name="link-player", description="Link a seeded player name to their Discord account")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(username="The name used when seeding (e.g. 'Zach Coury')", user="Their Discord account")
    async def link_player(self, interaction: discord.Interaction, username: str, user: discord.Member):
        success = await db.link_player(username, str(user.id))
        if success:
            await interaction.response.send_message(
                f"✅ Linked **{username}** to {user.mention}. Their legacy scores are now attached to their account.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"❌ Couldn't find a seeded player named **{username}**. Check the spelling matches exactly.",
                ephemeral=True,
            )

    @set_channel.error
    @reset.error
    @status.error
    @link_player.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("You need Administrator permission for that.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
