import discord
import operator
import io
import json
import aiohttp
import asyncio
import csv
#import datetime
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU

from datetime import datetime, timedelta

from queue import Queue

from discord.ext import commands, tasks
from discord.utils import find
from discord import Webhook,ui

from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import serverAdmin, serverOwner, MessageTemplates
from utility.embed_paginator import pages_of_embeds
from bot import TC_Cog_Mixin, super_context_menu

class TimeEdit():
    def __init__(self,bot:commands.Bot) -> None:
        self.bot=bot
    async def get_frequency(self, ctx):
        for i in range(0,10):
            await ctx.send("Select the frequency:\n 1. Daily\n 2. Weekly\n 3. Monthly")

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            choice = await self.bot.wait_for('message', check=check, timeout=60.0)

            if choice.content == "1":
                return DAILY
            elif choice.content == "2":
                return WEEKLY
            elif choice.content == "3":
                return MONTHLY
            else:
                await ctx.send("Invalid choice. Please try again.")
        raise Exception("Too many tries!")

    async def get_date(self, ctx, label):
        for i in range(0,10):
            await ctx.send(f"Enter the {label} date, or enter none (YYYY-MM-DD):")

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            date_message = await self.bot.wait_for('message', check=check, timeout=60.0)

            if date_message.content.lower() == 'none':
                return None

            try:
                date = datetime.datetime.strptime(date_message.content, "%Y-%m-%d")
                return date.date()
            except ValueError:
                await ctx.send("Invalid date format. Please try again.")
        raise Exception("Too many tries!")

    async def get_interval(self, ctx):
        for i in range(0,10):
            await ctx.send("Enter the interval:")

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            interval_message = await self.bot.wait_for('message', check=check, timeout=60.0)

            try:
                interval = int(interval_message.content)
                if interval > 0:
                    return interval
                else:
                    await ctx.send("Interval must be a positive integer.")
            except ValueError:
                await ctx.send("Invalid input. Please enter a positive integer.")
        raise Exception("Too many tries!")

    async def get_weekdays(self, ctx):
        weekdays = []
        await ctx.send("```Select the weekdays or type none, (separate by spaces):\n 1. Monday\n 2. Tuesday\n 3. Wednesday\n 4. Thursday\n 5. Friday\n 6. Saturday\n 7. Sunday```")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        choices_message = await self.bot.wait_for('message', check=check, timeout=60.0)

        choices = choices_message.content.split(" ")
        
        for choice in choices:
            if choice.lower()=='none':
                return None
            if choice == "1":
                weekdays.append(MO)
            elif choice == "2":
                weekdays.append(TU)
            elif choice == "3":
                weekdays.append(WE)
            elif choice == "4":
                weekdays.append(TH)
            elif choice == "5":
                weekdays.append(FR)
            elif choice == "6":
                weekdays.append(SA)
            elif choice == "7":
                weekdays.append(SU)
            else:
                await ctx.send(f"Ignoring invalid choice: {choice}")

        return weekdays
    

    async def get_time(self, ctx):
        for i in range(0,10):
            await ctx.send("Enter the time this rrule should execute at (HH:MM):")

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            time_message = await self.bot.wait_for('message', check=check, timeout=60.0)

            try:
                time = datetime.strptime(time_message.content, "%H:%M").time()
                return time
            except ValueError:
                await ctx.send("Invalid time format. Please try again.")
        raise Exception("Too many tries!")
class General(commands.Cog, TC_Cog_Mixin):
    """General commands"""
    def __init__(self, bot):
        self.helptext=""
        self.bot=bot
        self.init_context_menus()

    @commands.command()
    async def create_rrule(self, ctx):
        '''EXPERIMENTAL TEST.'''
        await ctx.send("""Welcome to the RRule Generator!
                       Please provide the following information:""")
        tedit=TimeEdit(ctx.bot)
        rule=None
        try:
            #this is legal with python 3.11, which is the version I deploy with.
            async with asyncio.timeout(8*60.0):
                freq = await tedit.get_frequency(ctx)
                start_date = await tedit.get_date(ctx, "start")
                end_date = await tedit.get_date(ctx, "end")
                interval = await tedit.get_interval(ctx)
                weekdays = await tedit.get_weekdays(ctx)
                time = await tedit.get_time(ctx)
                rule = rrule(freq, 
                             dtstart=start_date, until=end_date, 
                             interval=interval, byweekday=weekdays, 
                             byhour=time.hour, byminute=time.minute)
        except asyncio.TimeoutError:
            await ctx.send("Timeout occurred. Please try again.")
            return

        await ctx.send("RRule object created successfully:")
        await ctx.send(f"`{str(rule)}`, \n Will trigger next:" 
                       + str(rule.after(datetime.now()))
                       )
    @super_context_menu(name="Supercool")
    async def coooler(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await interaction.response.send_message(
            content="This command does nothing, it's to demonstrate context menu commands.",
            ephemeral=True)
        
    @super_context_menu(name="UserName")
    async def userexample(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await interaction.response.send_message(
            content=f"This user is named {user.display_name}",
            ephemeral=True)
        
    @app_commands.command(name="server_info", description="view the server data")
    async def info(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild = ctx.guild
        member_count = guild.member_count
        channel_count = len(guild.channels)
        blocked,can_see=0,0
        messagable, history_view=0,0
        c_mess,c_manage=0,0
        messagableperms=['send_messages','embed_links','attach_files','add_reactions','use_external_emojis','use_external_stickers','read_message_history','manage_webhooks' ]
        manageableperms=['manage_channels','manage_permissions']
        for channel in guild.text_channels:
            perms=channel.permissions_for(guild.me)
            
            if perms.view_channel:
                can_see+=1
                messageable_check=[]
                manageable_check=[]
                if perms.read_message_history:
                    history_view+=1
                if perms.send_messages:
                    for p, v in perms:
                        if v:
                            if p in messagableperms:
                                messageable_check.append(p)
                            if p in manageableperms:
                                manageable_check.append(p)
                    messagable+=1
                    if all(elem in messagableperms for elem in messageable_check):
                        c_mess+=1
                    if all(elem in manageableperms for elem in manageable_check):
                        c_manage+=1
                        
            else:
                blocked+=1

        view=f"Viewable:{can_see} channels.  \nArchivable: {history_view} channels."
        view2=f"Messagable: {messagable} channels.  \n Of which, {messagable-c_mess} channels have a restriction."
        desc=f"Members: {member_count}\n Channels: {channel_count}\n{view}\n{view2}"
        
        emb=await MessageTemplates.server_profile_message(ctx, description=desc,ephemeral=True )

    @app_commands.command(name="server_emoji_info", description="Print out all emojis in this server")
    @app_commands.guild_only()
    async def emojiinfo(self, interaction: discord.Interaction) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild = ctx.guild
        member_count = guild.member_count
        if guild:
            emojis=[]
            
            for emoji in guild.emojis:
                emoji_format = f"`<:{emoji.name}:{emoji.id}>`"
                if emoji.animated:
                    emoji_format = f"`<a:{emoji.name}:{emoji.id}>`"
                emojis.append(emoji_format)
            num_emojis = len(emojis)
            emoji_strings = [
            ' '.join([emoji for emoji in emojis[i:i+25]])
            for i in range(0, num_emojis, 25)
            ]
            elist=await MessageTemplates.server_profile_embed_list(ctx,emoji_strings)
            await pages_of_embeds(ctx,elist,ephemeral=True)

            
        else:
            await ctx.send("Guild not found.",ephemeral=True)
        



async def setup(bot):
    await bot.add_cog(General(bot))
