import asyncio
import discord
from discord.ext import commands, tasks
import re

from discord import app_commands

from sqlitedict import SqliteDict

from datetime import datetime, timezone
import gui
import utility
from utility import MessageTemplates
from bot import (
    TCBot,
    TCGuildTask,
    Guild_Task_Functions,
    StatusEditMessage,
    TC_Cog_Mixin,
)
import numpy as np




class PersonalServerConfigs(commands.Cog):
    def __init__(self, bot):
        self.helptext = (
            "This is for personal server configuration.  Work in progress."
        )
        self.bot = bot
        self.db = SqliteDict("./saveData/privateserverconfig.sqlite")
        
        

    def cog_unload(self):
        self.db.close()

    @commands.command()
    @commands.is_owner()
    @commands.guild_only()
    async def enable_personal_config(self, ctx):
        gid=f"g{ctx.guild.id}"
        if self.db.get(gid)==None:
            new={
                "private_channels":{}
            }
            self.db['guild_config'][gid]={
                "private_channels":{}
            }
            self.db['guild_config'].update({gid:{
                "private_channels":{}
            })
            self.db.commit()
            await ctx.send(str(self.db['guild_config'][gid]))
            self.db.commit()
            await ctx.send("Special config set up.")



    @commands.command()
    @commands.guild_only()
    async def create_private_channel(self, ctx):
        gid=f"g{ctx.guild.id}"
        if self.db['guild_config'].get(gid,None)==None:
            await ctx.send('no config detected...')
            return
        uid=f"u{ctx.author.id}"
        existing_channel = self.db.get('guild_config').get(gid)['private_channels'].get(uid,None)
        
        if existing_channel:
            await ctx.send(f"You already have a private channel: {existing_channel.mention}")
        else:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True,manage_channels=True)
            }
            new_channel = await ctx.guild.create_text_channel(f"{ctx.author.name}s-channel", overwrites=overwrites)
            await ctx.send(f"Private channel created: {new_channel.mention}")
            self.db.get('guild_config').get(gid)['private_channels'].update({uid:new_channel.id})

            


async def setup(bot):
    pc = PersonalServerConfigs(bot)
    await bot.add_cog(pc)
