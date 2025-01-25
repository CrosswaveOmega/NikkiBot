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
    @questmanage.command()
    async def add(self, ctx:commands.Context, channel: discord.ForumChannel, threshold: int):
        """Add a quest boardto the server."""
        existing = await Questboard.get_questboard(ctx.guild.id)
        if existing:
            await ctx.send("Questboard already exists for this server.")
            return
        

        mypost=await channel.create_thread(name="Welcome to the quest board!",content="Welcome to my quest board!")
        await Questboard.add_questboard(ctx.guild.id, channel.id,mypost.id)
        await ctx.send(
            f"Questboard added to {channel.mention} "
        )


    @questmanage.command(
        name="endquest",
        brief="end this quest now for whatever reason.",
    )
    async def badquest(self, ctx:commands.Context, reason:str="it's expired"):
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
        post:discord.Thread=ctx.channel
        await post.send(f"This quest is being cancelled, as {reason}!")
        await post.edit(archived=True,locked=True)

        
    




async def setup(bot):
    await bot.add_cog(QuestBoardCog(bot))
