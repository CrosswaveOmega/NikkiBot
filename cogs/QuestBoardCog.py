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
        self.kudo_limiter={}
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
            applied_tags=[next((tag for tag in channel.available_tags if tag.name == "Infomation"), None)])

        mypost.thread.id
        await Questboard.add_questboard(ctx.guild.id, channel.id,mypost.thread.id)
        await ctx.send(
            f"Questboard added to {channel.mention} "
        )

    @questmanage.command(
        name="edit_about",
        brief="end the guidelines for whatever reason.",
    )
    async def edit_my_post(self, ctx:commands.Context):
        """Add a quest boardto the server."""
        if ctx.channel.parent is None:
            await ctx.send("Not a forum channel!")
            return

        existing = await Questboard.get_questboard(ctx.guild.id)
        if not existing:
            await ctx.send("No questboard exists for this server.")
            return
        questb:discord.ForumChannel=await ctx.guild.fetch_channel(existing.channel_id)
        my_post:discord.Thread=questb.get_thread(existing.my_post)

        if not my_post:
            await ctx.send("My post isn't found!",ephemeral=True)
        async for message in my_post.history(limit=10,oldest_first=True):
            if message.author == ctx.bot.user:
              await message.edit( content='''
Welcome to the Quest Board!  
This is the channel where SEF members help out other SEF members py putting in requests!

Please make sure to tag your posts correctly!  The most helpful users will be placed on a leaderboard!

Quest Guidelines:

1. Quests posted here are meant to be completable!  Please post clear instructions for what you require others to accomplish!

2. When someone completes the quest, use the `/quest finish_quest` command and provide a reward to the user who solved the problem.

3. Don't abuse the reward system!  You will be punished.

4. Want to thank many people who helped?  Use `/quest kudos` and name them!
'''
                            )
        await ctx.send("Done!",ephemeral=True)

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
        await post.send(f"### This quest is cancelled, as {reason}!")
        await post.edit(archived=True,locked=True)
        if ctx.interaction:
            await ctx.send("Done!",ephemeral=True)



    @commands.hybrid_group(invoke_without_command=True)
    async def quest(self, ctx):
        """Quest management commands."""
        await ctx.send("Available subcommands tbd...")

    @quest.command(
        name="finish",
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


    @quest.command(
        name="kudos",
        brief="give kudos to someone in your thread!",
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
        
        isvalid=False
        membs=await post.fetch_members()
        for m in membs:
            if m.id==toreward.id:
                isvalid=True
        if not isvalid:
            await post.send(f"You must give kudos to someone responding to the quest!",epheremal=True)
            return

        if post.owner_id not in self.kudo_limiter:
            self.kudo_limiter[post.owner_id]={}
        if toreward.id not in self.kudo_limiter[post.owner_id]:
            self.kudo_limiter[post.owner_id][toreward.id]=datetime.datetime.now()
        else:

            now = datetime.datetime.now()
            diff = now - self.kudo_limiter[post.owner_id][toreward.id]
            cont= diff.total_seconds() >= 86400
            if not cont:
                await post.send(f"You already gave kudos to this person today...",epheremal=True)
                return

                    
            
        await QuestLeaderboard.update_user_score(
            ctx.guild.id,
            user_id=toreward.id,
            score=25,
            thank_count=0,
            quests_participated=0 
            )
        

        
        await post.send(f"Kudos have been given to {toreward.name}!")
        if ctx.interaction:
            await ctx.send("Done!",ephemeral=True)

        



        
    




async def setup(bot):
    await bot.add_cog(QuestBoardCog(bot))
