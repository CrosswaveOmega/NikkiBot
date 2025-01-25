import datetime
from typing import Union
import discord
from discord.ext import commands, tasks
from database import DatabaseSingleton
from cogs.dat_Questboard import (
    Questboard
)
from utility import (
    urltomessage,
)
import random
import asyncio



class QuestBoardCog(commands.Cog):
    """Based on the Star cog in RoboDanny."""

    def __init__(self, bot):
        self.bot = bot
        self.to_be_edited = {}
        self.lock = asyncio.Lock()
        self.server_emoji_caches = {}

    @commands.hybrid_group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def questmanage(self, ctx):
        """Questboard management commands."""
        await ctx.send("Available subcommands: add, remove, ...")

    @questmanage.hybrid_command()
    async def add(self, ctx, channel: discord.TextChannel, threshold: int):
        """Add a quest boardto the server."""
        existing = await Questboard.get_questboard(ctx.guild.id)
        if existing:
            await ctx.send("Questboard already exists for this server.")
            return

        await Questboard.add_starboard(ctx.guild.id, channel.id)
        await ctx.send(
            f"Questboard added to {channel.mention} "
        )


    @questmanage.hybrid_command(
        name="endquest",
        brief="end this quest now for whatever reason.",
    )
    async def badquest(self, ctx:commands.Context, reason:str):
        """Add a quest boardto the server."""
        if ctx.channel.parent is None:
            await ctx.send("Not a forum channel!")
            return

        existing = await Questboard.get_questboard(ctx.guild.id)
        if not existing:
            await ctx.send("No questboard exists for this server.")
            return

        if ctx.channel.parent.id!=existing.channel_id:
            await ctx.send("Not a questboard.")
            return

        
    




async def setup(bot):
    await bot.add_cog(QuestBoardCog(bot))
