import datetime
from typing import Tuple, Union
import discord
from discord.ext import commands, tasks
from database import DatabaseSingleton
from cogs.dat_Questboard import QuestLeaderboard, Questboard
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
        self.kudo_limiter = {}
        self.lock = asyncio.Lock()
        self.server_emoji_caches = {}
        self.cached={}
    

    async def checkboard_status(self,ctx):
        if ctx.channel.parent is None:
            return 0,False,False
        existing_questboard = await Questboard.get_questboard(ctx.guild.id)
        if not existing_questboard:
            return 1,False,False
        if ctx.channel.parent.id != existing_questboard.channel_id:
            return 2,existing_questboard,False
        questb: discord.ForumChannel = await ctx.guild.fetch_channel(
            existing_questboard.channel_id
        )
        return 8,existing_questboard, questb
    
    async def questboard_command_checks(self, ctx:commands.Context)->Tuple[Union[Questboard,bool],Union[discord.ForumChanne,bool]]:
        """
        Performs a series of checks to ensure that the command is being used
        in a valid questboard context.

        Args:
            ctx (commands.context): The context of the command invocation.

        Returns:
            Tuple[Union[Questboard, bool], Union[discord.ForumChannel, bool]]:
                A tuple containing the Questboard object and the associated
                Discord Forum Channel if all checks pass, otherwise False values.
        """
        #Ensure this is in a forum channel.
        res,questboard,questb=await self.checkboard_status(ctx)
        if res==0:
            await ctx.send("Not a forum channel!", ephemeral=True)
            return False,False
        if res==1:
            await ctx.send("No questboard exists for this server.", ephemeral=True)
            return False,False
        if res==2:
            await ctx.send("This command must be used in a questboard.", ephemeral=True)
            return questboard,False

        return questboard, questb


        
    @commands.hybrid_group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def questmanage(self, ctx):
        """Questboard management commands."""
        await ctx.send("Available subcommands: add, remove, ...")

    @commands.has_permissions(manage_guild=True)
    @questmanage.command()
    async def add(
        self, ctx: commands.Context, channel: discord.ForumChannel, threshold: int
    ):
        """Add a quest boardto the server."""
        existing_questboard = await Questboard.get_questboard(ctx.guild.id)
        if existing_questboard:
            await ctx.send("Questboard already exists for this server.")
            return
        mypost = await channel.create_thread(
            name="Welcome to the quest board!",
            content="Welcome to the quest board!",
            applied_tags=[
                next(
                    (tag for tag in channel.available_tags if tag.name == "Infomation"),
                    None,
                )
            ],
        )
        mypost.thread.id
        await Questboard.add_questboard(ctx.guild.id, channel.id, mypost.thread.id)
        await ctx.send(f"Questboard added to {channel.mention} ")

    @questmanage.command(
        name="edit_about",
        brief="end the guidelines for whatever reason.",
    )
    async def edit_my_post(self, ctx: commands.Context):
        """Add a quest boardto the server."""
        questboard,questchannel=await self.questboard_command_checks(ctx)
        if not questboard or not questchannel:
            return
        
        my_post: discord.Thread = questchannel.get_thread(questboard.my_post)

        if not my_post:
            await ctx.send("My post isn't found!", ephemeral=True)
        async for message in my_post.history(limit=10, oldest_first=True):
            if message.author == ctx.bot.user:
                await message.edit(
                    content="""
Welcome to the Quest Board!  
This is the channel where SEF members help out other SEF members by putting in requests!

Please make sure to tag your posts correctly!  The most helpful users will be placed on a leaderboard!

Quest Guidelines:

1. Quests posted here are meant to be completable!  
 * **Please post clear instructions for what you require others to accomplish!**
2. When someone completes the quest, use the `/quest finish_quest` command and provide a reward to the user who solved the problem.
3. Don't abuse the reward system!  You will be punished.
4. Want to thank many people who helped?  Use `/quest kudos` and name them!

"""
                )
        await ctx.send("Done!", ephemeral=True)

    @commands.has_permissions(manage_guild=True)
    @questmanage.command(
        name="endquest",
        brief="end this quest now for whatever reason.",
    )
    async def badquest(self, ctx: commands.Context, reason: str = "it's expired"):
        """Add a quest boardto the server."""
        questboard,questchannel=await self.questboard_command_checks(ctx)
        if not questboard or not questchannel:
            return
        post: discord.Thread = ctx.channel
        await post.send(f"### This quest is cancelled, as {reason}!")
        await post.edit(
            archived=True,
            locked=True,
            applied_tags=[
                next(
                    (
                        tag
                        for tag in questchannel.available_tags
                        if tag.name == "closed"
                    ),
                    None,
                )
            ],
        )
        if ctx.interaction:
            await ctx.send("Done!", ephemeral=True)


    @commands.has_permissions(manage_guild=True)
    @questmanage.command(
        name="leaderboard",
        brief="Show the quest leaderboard!",
    )
    async def showleaderboard(self, ctx: commands.Context):
        """Add a quest boardto the server."""
        questboard,questchannel=await self.questboard_command_checks(ctx)
        if not questboard or not questchannel:
            return
        leaderboard=await QuestLeaderboard.get_leaderboard_for_guild(ctx.guild.id)
        outs=[]
        for n, e in enumerate(leaderboard):
            user=ctx.guild.get_member(e.user_id)
            outv=f"{n}. {user.display_name}: {e.score}, {e.thank_count}"
            outs.append(outv)
        await ctx.send(content="\n".join(outs))


    async def archive_quest(self,post:discord.Thread):
        users={}
        async for message in post.history(limit=100, oldest_first=False):
            if message.author.id != post.owner_id:
                att=0 or len(message.attachments)
                if not message.author.id in users:
                    users[message.author.id]={"m":0,"a":0,"q":1}
                users[message.author.id]["m"]+=1
                users[message.author.id]["a"]+=att

        for uid,val in users.items():
            await QuestLeaderboard.update_user_score(
            post.guild.id,
            user_id=uid,
            score=1,
            thank_count=0,
            quests_participated=1,
            messages=val["m"],
            files=val["a"]
            
        )


                
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
    async def end_quest(self, ctx: commands.Context, toreward: discord.Member):
        """End the quest and give a reward."""
        questboard,questchannel=await self.questboard_command_checks(ctx)
        if not questboard or not questchannel:
            return

        post: discord.Thread = ctx.channel

        if ctx.author.id != post.owner_id:
            await ctx.send("You are not the post owner.", ephemeral=True)
            return
        if toreward.id == post.owner_id:
            await ctx.send("You can't reward yourself.", ephemeral=True)
            return
        await QuestLeaderboard.update_user_score(
            ctx.guild.id,
            user_id=toreward.id,
            score=100,
            thank_count=1,
            quests_participated=1,
        )

        await post.send("### Success!  This quest had been transgressed with finesse!")
        if ctx.interaction:
            await ctx.send("Done!", ephemeral=True)
        await self.archive_quest(post)
        await post.edit(
            archived=True,
            locked=True,
            applied_tags=[
                next(
                    (
                        tag
                        for tag in ctx.channel.parent.available_tags
                        if tag.name == "complete"
                    ),
                    None,
                )
            ],
        )
        

    @quest.command(
        name="kudos",
        brief="give kudos to someone in your thread!",
    )
    @app_commands.describe(
        toreward="The user to reward.",
    )
    async def kudos(self, ctx: commands.Context, toreward: discord.Member):
        """give kudos to a user."""
        questboard,questchannel=await self.questboard_command_checks(ctx)
        if not questboard or not questchannel:
            return

        post: discord.Thread = ctx.channel

        if ctx.author.id != post.owner_id:
            await ctx.send(f"You are not the post owner.", ephemeral=True)
            return

        if toreward.id == post.owner_id:
            await ctx.send(f"You can't reward yourself.", ephemeral=True)
            return

        isvalid = False
        membs = await post.fetch_members()
        for m in membs:
            if m.id == toreward.id:
                isvalid = True
        if not isvalid:
            await ctx.send(
                f"You must give kudos to someone responding to the quest!",
                ephemeral=True,
            )
            return

        if post.owner_id not in self.kudo_limiter:
            self.kudo_limiter[post.owner_id] = {}
        if toreward.id not in self.kudo_limiter[post.owner_id]:
            self.kudo_limiter[post.owner_id][toreward.id] = datetime.datetime.now()
        else:
            now = datetime.datetime.now()
            diff = now - self.kudo_limiter[post.owner_id][toreward.id]
            cont = diff.total_seconds() >= 86400
            if not cont:
                await ctx.send(
                    f"You already gave kudos to this person today...", ephemeral=True
                )
                return

        await QuestLeaderboard.update_user_score(
            ctx.guild.id,
            user_id=toreward.id,
            score=25,
            thank_count=0,
            quests_participated=0,
        )

        await post.send(f"Kudos have been given to {toreward.name}!")
        if ctx.interaction:
            await ctx.send("Done!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(QuestBoardCog(bot))
