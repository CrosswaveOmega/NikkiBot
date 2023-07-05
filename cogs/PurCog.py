from typing import Literal, Optional
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
from discord import EntityType, PrivacyLevel, Webhook,ui

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
    'ban': "This server is banned from using my AI due to repeated violations.",
    'cooldown': "There's a one minute delay between messages."
},
'user':
{
    'messagelimit': "You have reached the daily message limit, please try again tomorrow.",
    'ban': "You are forbidden from using my AI due to conduct.",
    'cooldown': "There's a one minute delay between messages, slow down man!"
}
}
from gptfunctionutil import *
from .StepCalculator import evaluate_expression

class MyLib(GPTFunctionLibrary):
    @AILibFunction(name='get_time',description='Get the current time and day in UTC.')
    @LibParam(comment='An interesting, amusing remark.')
    async def get_time(self,comment:str):
        #This is an example of a decorated coroutine command.
        return f"{comment}\n{str(discord.utils.utcnow())}"
    #pass



async def message_check(bot:TCBot,message:discord.Message,mylib:GPTFunctionLibrary=None):
    ctx=await bot.get_context(message)
    permissions = message.channel.permissions_for(message.channel.guild.me)
    if permissions.send_messages:
        pass
    else:
        raise Exception(f"{message.channel.name}:{message.channel.id} send message permission not enabled.")

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
        emb=discord.Embed(title="Audit",description=f"```{message.content}```")
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
    chat.add_message('user',message.content)
    if mylib!=None:
        forcecheck=mylib.force_word_check(message.content)
        if forcecheck:
            chat.functions=forcecheck
            chat.function_call={'name':forcecheck[0]['name']}
        else:
            chat.functions=mylib.get_schema()
            chat.function_call='auto'
    #Call API
    async with message.channel.typing():
        res=await bot.gptapi.callapi(chat)
    if res.get('err',False):
        err=res[err]
        error=purgpt.error.PurGPTError(err,json_body=res)
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
        function=None
        messageresp=None
        if i['finish_reason']=='function_call' or 'function_call' in i['message']:
            functiondict=i['message']['function_call']
            output=await mylib.call_by_dict_ctx(ctx,functiondict)
            
            resp= output
            content=resp
            function=str(i['message']['function_call'])
        if isinstance(content,str):
            page=commands.Paginator(prefix='',suffix=None)
            for p in content.split("\n"):
                page.add_line(p)
            messageresp=None
            for pa in page.pages:
                ms=await message.channel.send(pa)
                if messageresp==None:messageresp=ms
        elif isinstance(content,discord.Message):
            messageresp=content
            content=messageresp.content
        else:
            messageresp=await message.channel.send('No output from this command.')
            content='No output from this command.'

        if function:
            profile.add_message_to_chain(messageresp.id,messageresp.created_at,role=role,content='', function=function)
        profile.add_message_to_chain(messageresp.id,messageresp.created_at,role=role,content=content)

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
        self.flib=MyLib()
        self.flib.do_expression=True
        self.flib.my_math_parser=evaluate_expression
        self.walked=False

    @commands.hybrid_group(fallback="view")
    @app_commands.default_permissions(manage_messages=True,manage_channels=True)
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True,manage_channels=True)
    async def ai_setup(self, ctx):
        """This family of commands is for setting up the ai in your server."""
        guild=ctx.guild
        guildid=guild.id
        profile=ServerAIConfig.get_or_new(guildid)

        await MessageTemplates.server_ai_message(ctx,"Here is your server's data.")
    @ai_setup.command(
        name="clear_history",
        brief="clear ai chat history."
    )

    async def chear_history(self, ctx):
        guild=ctx.guild
        guildid=guild.id
        profile=ServerAIConfig.get_or_new(guildid)
        
        await MessageTemplates.server_ai_message(ctx,"purging")
        profile.clear_message_chains()
        await MessageTemplates.server_ai_message(ctx,"Data purged")

    @commands.hybrid_command(name="ai_functions",description="Get a list of ai functions.")
    async def ai_functions(self,ctx):
        schema=self.flib.get_schema()

        def generate_embed(command_data):
            name = command_data['name']
            description = command_data['description']
            parameters = command_data['parameters']['properties']

            embed = discord.Embed(title=name, description=description)

            for param_name, param_data in parameters.items():
                param_fields = '\n'.join([f"{key}: {value}" for key, value in param_data.items()])
                embed.add_field(name=param_name, value=param_fields[:1020], inline=False)
            return embed
        embeds = [generate_embed(command_data) for command_data in schema]
        if ctx.interaction:
            await pages_of_embeds(ctx, embeds,ephemeral=True)
        else:
            await pages_of_embeds(ctx, embeds)

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
        """Ban a user from using the AI API."""
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
    async def aibanserver(self, interaction: discord.Interaction, serverid:int) -> None:
        """Ban a entire server user using the AI API."""
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
        name="add_ai_channel",
        description="add a channel that Nikki will talk freely in."
    )
    async def add_ai_channel(self, ctx, target_channel:discord.TextChannel):
        guild=ctx.guild
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
        await MessageTemplates.server_ai_message(ctx,f"Understood.  Whenever a message is sent in <#{target_channel.id}>, I'll respond to it.")
    @ai_setup.command(
        name="remove_ai_channel",
        description="use to stop Nikki from talking in an added AI Channel."
    )
    @app_commands.describe(
        target_channel='channel to disable.'
    )
    async def remove_ai_channel(self, ctx, target_channel:discord.TextChannel):  
        '''remove a channel.'''
        guild=ctx.guild
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
        '''Listener that will invoke the AI upon a message.'''
        if message.author.bot: return #Don't respond to bot messages.
        if not message.guild: return #Only work in guilds
        for p in self.bot.command_prefix:
            if message.content.startswith(p): return 
        try:
            if not self.walked:
                self.flib.add_in_commands(self.bot)
            profile=ServerAIConfig.get_or_new(message.guild.id)
            if self.bot.user.mentioned_in(message) and not message.mention_everyone:
                await message_check(self.bot,message, mylib=self.flib)
            else:
                if profile.has_channel(message.channel.id):
                    await message_check(self.bot,message,mylib=self.flib)
        except Exception as error:           
            try:
                emb=MessageTemplates.get_error_embed(title=f"Error with your query!",description=f"Something went wrong with the AI.")
                await message.channel.send(embed=emb)
            except Exception as e:
                
                try:
                    myperms= message.guild.system_channel.permissions_for(message.guild.me)
                    if myperms.send_messages:
                        await message.channel.send('I need to be able to send messages in a channel to use this feature.')
                except e:
                    pass
                        
                await self.bot.send_error(e,title=f"Could not send message",uselog=True)
            await self.bot.send_error(error,title=f"AI Responce error",uselog=True)

    

    

        



async def setup(bot):
    await bot.add_cog(AICog(bot))
