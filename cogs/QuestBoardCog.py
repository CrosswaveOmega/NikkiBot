import datetime
from typing import Union
import discord
from discord.ext import commands, tasks
from database import DatabaseSingleton
from cogs.dat_Questboard import (
    QuestLeaderboard,
    Questboard
)
from utility import (
    urltomessage,
)
import random
import asyncio
from discord import app_commands
from discord.app_commands import Choice



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
        

        mypost=await channel.create_thread(
            name="Welcome to the quest board!",
            content="Welcome to the quest board!",
            applied_tags=[1332821535198806036])
        mypost.thread.id
        await Questboard.add_questboard(ctx.guild.id, channel.id,mypost.thread.id)
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

    @commands.hybrid_group(invoke_without_command=True)
    async def quest(self, ctx):
        """Quest management commands."""
        await ctx.send("Available subcommands tbd...")

    @quest.command(
        name="finish_quest",
        brief="end this quest and reward someone",
    )
    @app_commands.describe(
        toreward="The user to reward.",
    )
    async def end_quest(self, ctx:commands.Context, toreward:discord.Member):
        """Add a quest boardto the server."""
        if ctx.channel.parent is None:
            await ctx.send("Not a forum channel!")
            return

        existing = await Questboard.get_questboard(ctx.guild.id)
        if not existing:
            await ctx.send("No questboard exists for this server.")
            return

        if ctx.channel.parent.id!=existing.channel_id:
            await ctx.send("Not in the questboard.")
            return
        
        post:discord.Thread=ctx.channel
        
        if ctx.author.id!=post.owner_id:
            await post.send(f"You are not the post owner.",epheremal=True)
            return
        
        if toreward.id==post.owner_id:
            await post.send(f"You can't reward yourself.",epheremal=True)
            return
        await QuestLeaderboard.update_user_score(
            ctx.guild.id,
            user_id=toreward.id,
            score=100,
            thank_count=1,
             quests_participated=1 )
        

        
        await post.send(f"### Success!  This quest had been transgressed with finesse!")

        await post.edit(archived=True,locked=True)
        if ctx.interaction:
            await ctx.send("Done!",ephemeral=True)

        



        
    




async def setup(bot):
    await bot.add_cog(QuestBoardCog(bot))
