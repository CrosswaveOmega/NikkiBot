from typing import Literal
import discord
import operator
import io
import json
import aiohttp
import asyncio
import re
#import datetime
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU

from datetime import datetime, time, timedelta
import time
from queue import Queue

from discord.ext import commands, tasks
from discord.utils import find
from discord import Webhook,ui

from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import MessageTemplates, RRuleView, formatutil
from utility.embed_paginator import pages_of_embeds
from bot import TCBot,TC_Cog_Mixin, super_context_menu
import purgpt
import purgpt.error
from assets import AssetLookup
from database.database_ai import AuditProfile, ServerAIConfig

lock = asyncio.Lock()
reasons={'server':{
    'messagelimit': "This server has reached the daily message limit, please try again tomorrow.",
    'ban': "This server is banned from using my AI due to violations.",
    'cooldown': "There's a one minute delay between messages."
},
'user':
{
    'messagelimit': "You have reached the daily message limit, please try again tomorrow.",
    'ban': "You are forbidden from using my AI due to conduct.",
    'cooldown': "There's a one minute delay between messages, slow down man!"
}
} 
async def message_check(bot:TCBot,message):

    guild=message.guild
    user=message.author
    if len(message.clean_content)>2000:
        await message.channel.send("This message is too big.")
        return
    async with lock:
        serverrep,userrep=AuditProfile.get_or_new(guild,user)
        serverrep.checktime()
        userrep.checktime()

        ok, reason=serverrep.check_if_ok()
        if not ok:
            await message.channel.send(reasons["server"][reason])
            return
        ok, reason=userrep.check_if_ok()
        if not ok:
            await message.channel.send(reasons["user"][reason])
            return
        serverrep.modify_status()
        userrep.modify_status()
    profile=ServerAIConfig.get_or_new(guild.id)
    audit_channel=AssetLookup.get_asset("monitor_channel")

    if audit_channel:
        emb=discord.Embed(title="Audit",description=message.clean_content)
        emb.add_field(name="Server Data",value=f"{guild.name}, \nServer ID: {guild.id}",inline=False)
        emb.add_field(name="User Data",value=f"{user.name}, \n User ID: {user.id}",inline=False)
        target=bot.get_channel(int(audit_channel))
        await target.send(embed=emb)
    
    profile.prune_message_chains()
    chain=profile.list_message_chains()
    mes=[c.to_dict() for c in chain]
    chat=purgpt.ChatCreation()
    for f in mes:
        chat.add_message(f['role'],f['content'])
    chat.add_message('user',message.clean_content)
    #Call API
    async with message.channel.typing():
        res=await bot.gptapi.callapi(chat)
    if res.get('err',False):
        error=purgpt.error.PurGPTError(str(res))
        raise error
    profile.add_message_to_chain(
        message.id,message.created_at,
        role='user',
        name=re.sub(r'[^a-zA-Z0-9_]', '', user.name),
        content=message.clean_content)

    result=res['choices']
    bot.logs.info(str(res))
    for i in result:
        
        role=i['message']['role']
        content=i['message']['content']
        page=commands.Paginator(prefix='',suffix=None)
        for p in content.split("\n"):
            page.add_line(p)
        messageresp=None
        for pa in page.pages:
            ms=await message.channel.send(pa)
            if messageresp==None:messageresp=ms
        profile.add_message_to_chain(messageresp.id,messageresp.created_at,role=role,content=messageresp.clean_content)
        emb=discord.Embed(title="Audit",description=messageresp.clean_content)
        

        emb.add_field(name="Server Data",value=f"{guild.name}, \nServer ID: {guild.id}",inline=False)
        emb.add_field(name="User Data",value=f"{user.name}, \n User ID: {user.id}",inline=False)
        target=bot.get_channel(int(audit_channel))
        await target.send(embed=emb)
    bot.database.commit()




    
class AICog(commands.Cog, TC_Cog_Mixin):
    """General commands"""
    def __init__(self, bot):
        self.helptext=""
        self.bot=bot
        self.init_context_menus()

    
    @commands.hybrid_group(fallback="view")
    @app_commands.default_permissions(manage_messages=True,manage_channels=True)
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True,manage_channels=True)
    async def ai_setup(self, ctx):
        """This family of commands is for setting up the ai in your server."""
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        profile=ServerAIConfig.get_or_new(guildid)

        await MessageTemplates.server_ai_message(ctx,"Here is your server's data.")
    
    @ai_setup.command(
        name="add_ai_channel",
        brief="add a channel that Nikki can talk freely in."
    )
    async def add_ai_channel(self, ctx, target_channel:discord.TextChannel):
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        profile=ServerAIConfig.get_or_new(guildid)
        chanment=[target_channel]
        if len(chanment)>=1:
            for chan in chanment:
                profile.add_channel(chan.id)
        else:
            await MessageTemplates.server_ai_message(ctx,"?")
            return 
        self.bot.database.commit()
        await MessageTemplates.server_ai_message(ctx,"I will start listening there, ok?'")

    @commands.command(brief="Update user or server api limit [server,user],id,limit")
    @commands.is_owner()
    async def increase_limit(self,ctx,type:Literal['server','user'],id:int,limit:int):
        '''"Update user or server api limit `[server,user],id,limit`"'''
        if type=='server':
            profile=AuditProfile.get_server(id)
            if profile:
                profile.DailyLimit=limit
                self.bot.database.commit()
                await ctx.send("done")
            else:
                await ctx.send("server not found.")
        elif type=='user':
            profile=AuditProfile.get_user(id)
            if profile:
                profile.DailyLimit=limit
                self.bot.database.commit()
                await ctx.send("done")
            else:
                await ctx.send("user not found.")
        
        
    @app_commands.command(name="ban_user", description="Ban a user from using my AI.", extras={"homeonly":True})
    @app_commands.describe(userid='user id')
    async def aiban(self, interaction: discord.Interaction, userid:int) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        if interaction.user!=self.bot.application.owner:
            await ctx.send("This command is owner only, buddy.")
            return
        profile=AuditProfile.get_user(userid)
        if profile:
            profile.ban()
            await ctx.send(f"Good riddance!  User <@{userid}> has been banned.")
        else:
            await ctx.send(f"I see no user by that name.")


    @app_commands.command(name="ban_server", description="Ban a server from using my AI.", extras={"homeonly":True})
    @app_commands.describe(serverid='server id to ban.')
    #@app_commands.guilds(discord.Object(id=AssetLookup.get_asset('homeguild')))
    async def aibanserver(self, interaction: discord.Interaction, serverid:int) -> None:
        """get bot info for this server"""
        ctx: commands.Context = await self.bot.get_context(interaction)
        if interaction.user!=self.bot.application.owner:
            await ctx.send("This command is owner only, buddy.")
            return
        profile=AuditProfile.get_server(serverid)
        if profile:
            profile.ban()
            await ctx.send(f"Good riddance!  The server with id {id} has been banned.")
        else:
            await ctx.send(f"I see no server by that name.")
    
    @ai_setup.command(
        name="remove_ai_channel",
        brief="use to stop Nikki from talking in an added AI Channel."
    )
    async def remove_ai_channel(self, ctx, target_channel:discord.TextChannel):  

        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        profile=ServerAIConfig.get_or_new(guildid)
        chanment=[target_channel]
        if len(chanment)>=1:
            for chan in chanment:
                profile.remove_channel(chan.id)
        else:
            await MessageTemplates.server_ai_message(ctx,"?")
            return 
        self.bot.database.commit()
        await MessageTemplates.server_ai_message(ctx,"I will stop listening there, ok?  Pings will still work, though.")
    
    @commands.Cog.listener()
    async def on_message(self,message:discord.Message):
        '''send a message'''
        if message.author.bot: return
        if not message.guild: return
        try:
            profile=ServerAIConfig.get_or_new(message.guild.id)
            if self.bot.user.mentioned_in(message):
                await message_check(self.bot,message)
            else:
                if profile.has_channel(message.channel.id):
                    await message_check(self.bot,message)
        except Exception as error:
            errormess=str(error)[:4000]
            emb=MessageTemplates.get_error_embed(title=f"Error with your query!",description=f"{errormess}")
            await self.bot.send_error(error,title=f"AI Responce error",uselog=True)
            try:
                await message.channel.send(embed=emb)
            except Exception as e:
                await self.bot.send_error(e,title=f"Could not send message",uselog=True)
        

    

    

        



async def setup(bot):
    await bot.add_cog(AICog(bot))
