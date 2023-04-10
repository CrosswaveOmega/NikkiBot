import discord
import operator
import io
import json
import aiohttp
import asyncio
import csv
#import datetime
from datetime import datetime, timedelta

from queue import Queue

from discord.ext import commands, tasks
from discord.utils import find
from discord import Webhook,ui

from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import serverAdmin, serverOwner
from utility.embed_paginator import pages_of_embeds
''''''



class HelpSelect(discord.ui.Select):
    def __init__(self,myhelp):
        self.myhelp=myhelp
        ctx = self.myhelp.context
        bot = ctx.bot
        self.cogs = bot.cogs
        options=[]
        for i, v in self.cogs.items():
            options.append(discord.SelectOption(label=v.qualified_name,description="This is cog {}".format(v.qualified_name)))
           
            print(i)

        super().__init__(placeholder="Select a cog",max_values=1,min_values=1,options=options)
    async def callback(self, interaction: discord.Interaction):
        value=self.values[0]
        
        for i, v in self.cogs.items():
            if value==v.qualified_name:
                myembed=await self.myhelp.get_cog_help_embed(v)
                await interaction.response.edit_message(content="showing cog help",embed=myembed)

class SelectView(discord.ui.View):
    def __init__(self, *, timeout = 180, myhelp=None):
        super().__init__(timeout=timeout)
        self.add_item(HelpSelect(myhelp))



class SetupCommands(app_commands.Group):
    pass
class Setup(commands.Cog):
    """The component where you enable/disable other components."""
    def __init__(self, bot):
        self.helptext="This section is for enabling and disabling specific bot features for your server."
        self.bot=bot


    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        bot=self.bot

        await bot.tree.sync(guild=guild)
        if guild.system_channel!=None:
            await guild.system_channel.send("Hi, thanks for inviting me to your server! ")

    @commands.hybrid_group(name="accordsetup")
    async def setup(self, ctx: commands.Context) -> None:
        """This group is to setup the bot in your server!
        """
        await self.sub_command(ctx)

async def setup(bot):
    await bot.add_cog(Setup(bot))
