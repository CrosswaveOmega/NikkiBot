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
from utility import serverAdmin, serverOwner, MessageTemplates
from utility.embed_paginator import pages_of_embeds
from bot import TC_Cog_Mixin, super_context_menu

class General(commands.Cog, TC_Cog_Mixin):
    """General commands"""
    def __init__(self, bot):
        self.helptext=""
        self.bot=bot
        self.init_context_menus()

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
