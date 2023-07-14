import base64
from typing import Any, Literal, Optional
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
import utility.hash as hash
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
from .AICalling import AIMessageTemplates

class MyLib(GPTFunctionLibrary):
    @AILibFunction(name='get_time',description='Get the current time and day in UTC.')
    @LibParam(comment='An interesting, amusing remark.')
    async def get_time(self,comment:str):
        #This is an example of a decorated coroutine command.
        return f"{comment}\n{str(discord.utils.utcnow())}"
    #pass

async def precheck_context(ctx:commands.Context)->bool:
    '''Evaluate if a message should be processed.'''
    guild,user=ctx.guild,ctx.author

    async with lock:
        serverrep,userrep=AuditProfile.get_or_new(guild,user)
        serverrep.checktime()
        userrep.checktime()

        ok, reason=serverrep.check_if_ok()
        if not ok:
            await ctx.channel.send(reasons["server"][reason])
            return False
        ok, reason=userrep.check_if_ok()
        if not ok:
            await ctx.channel.send(reasons["user"][reason])
            return False
        serverrep.modify_status()
        userrep.modify_status()
    return True

async def process_result(ctx:commands.Context,result:Any,mylib:GPTFunctionLibrary):
    '''
    process the result.  Will either send a message, or invoke a function.  
    
    
    When a function is invoked, the output of the function is added to the chain instead.
    '''
    if result.model=='you':
        i=result.choices[0]
        role,content=i.message.role,i.message.content
        messageresp=await ctx.channel.send(content)

        return role,content,messageresp,None

    i=result.choices[0]
    role,content=i.message.role,i.message.content
    messageresp=None
    function=None
    finish_reason=i.get('finish_reason',None)
    if finish_reason =='function_call' or 'function_call' in i['message']:
        #Call the corresponding funciton, and set that to content.
        functiondict=i.message.function_call 
        name,args=mylib.parse_name_args(functiondict)
        audit=await AIMessageTemplates.add_function_audit(
            ctx,
            functiondict,
            name,
            args
        )
        function=str(i['message']['function_call'])
        resp= await mylib.call_by_dict_ctx(ctx,functiondict)
        content=resp
    if isinstance(content,str):
        #Split up content by line if it's too long.
        page=commands.Paginator(prefix='',suffix=None)
        for p in content.split("\n"):
            page.add_line(p)
        messageresp=None
        for pa in page.pages:
            ms=await ctx.channel.send(pa)
            if messageresp==None:messageresp=ms
    elif isinstance(content,discord.Message):
        messageresp=content
        content=messageresp.content
    else:
        print(result,content)
        messageresp=await ctx.channel.send('No output from this command.')
        content='No output from this command.'
    return role,content,messageresp, function


async def ai_message_invoke(bot:TCBot,message:discord.Message,mylib:GPTFunctionLibrary=None):
    '''Evaluate if a message should be processed.'''
    permissions = message.channel.permissions_for(message.channel.guild.me)
    if permissions.send_messages:
        pass
    else:
        raise Exception(f"{message.channel.name}:{message.channel.id} send message permission not enabled.")
    if len(message.clean_content)>2000:
        await message.channel.send("This message is too big.")
        return False
    ctx=await bot.get_context(message)
    if await ctx.bot.gptapi.check_oai(ctx):
        return

    botcheck=await precheck_context(ctx)
    if not botcheck:
        return
    guild,user=message.guild,message.author
    #Get the 'profile' of the active guild.
    profile=ServerAIConfig.get_or_new(guild.id)
    #prune message chains with length greater than X
    profile.prune_message_chains()
    #retrieve the saved messages
    chain=profile.list_message_chains()
    #Convert into a list of messages
    mes=[c.to_dict() for c in chain]
    #create new ChatCreation
    chat=purgpt.ChatCreation(model="gpt-3.5-turbo-0613")
    for f in mes[:10]: #Load old messags into ChatCreation
        chat.add_message(f['role'],f['content'])
    #Load current message into chat creation.
    chat.add_message('user',message.content)

    #Load in functions
    if mylib!=None:
        forcecheck=mylib.force_word_check(message.content)
        if forcecheck:
            chat.functions=forcecheck
            chat.function_call={'name':forcecheck[0]['name']}
        else:
            chat.functions=mylib.get_schema()
            chat.function_call='auto'

    audit=await AIMessageTemplates.add_user_audit(
        ctx, chat
    )



    async with message.channel.typing():
        #Call the API.
        result=await bot.gptapi.callapi(chat)

    if result.get('err',False):
        err=result[err]
        error=purgpt.error.PurGPTError(err,json_body=result)
        raise error
    #only add messages after they're finished processing.
    
    bot.logs.info(str(result))
    #Process the result.
    role, content, messageresp,func=await process_result(ctx,result,mylib)
    profile.add_message_to_chain\
    (
        message.id,message.created_at,
        role='user',
        name=re.sub(r'[^a-zA-Z0-9_]', '', user.name),
        content=message.clean_content
    )
    #Add 
    if func:
        profile.add_message_to_chain\
        (
            messageresp.id,
            messageresp.created_at,
            role=role,
            content='', 
            function=func
        )
    profile.add_message_to_chain(messageresp.id,messageresp.created_at,role=role,content=content)

    audit=await AIMessageTemplates.add_resp_audit(
        ctx,
        messageresp,
        result
    )
    
    bot.database.commit()



async def download_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.read()
                return io.BytesIO(data)

    
class AICog(commands.Cog, TC_Cog_Mixin):
    """General commands"""
    def __init__(self, bot):
        self.helptext="This is Nikki's AI features"
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
        profile=ServerAIConfig.get_or_new(guild.id)
        
        await MessageTemplates.server_ai_message(ctx,"purging")
        messages=profile.clear_message_chains()
        await MessageTemplates.server_ai_message(ctx,f"{messages} purged")

    mc=app_commands.Group(name="image_ai",description='Generate images with DALL-E.')
    @mc.command(name="generate_image",description="make a dalle image.")
    async def make_image(self,inter:discord.Interaction,prompt:str,num:int=1,size:Literal['256x256','512x512','1024x1024']='256x256'):
        ctx=await self.bot.get_context(inter)
        if not ctx.guild: return
        user_id=ctx.author.id
        targetid,num2=hash.hash_string(str(user_id),hashlen=16,hashset=hash.Hashsets.base64)
        if len(prompt)>=1000:
            await ctx.send("Prompt too long.",ephemeral=True)
            return
        if not 0<num<=10:
            await ctx.send("Invalid number of generations.",ephemeral=True)
            return
        precheck=precheck_context(ctx)
        if not precheck:
            await ctx.send("Precheck failed.",ephemeral=True)
            return
        img=purgpt.object.Image(
            prompt=prompt,
            n=num,
            size=size
        )
        
        message=await ctx.send(f"Generating image{'s' if num>1 else ''}...")
        async with ctx.channel.typing():
            #Call the API.
            result=await ctx.bot.gptapi.callapi(img)
        for data in result.data:
            myimg=await download_image(data['url'])
            # Create a discord.File object using the image_bytes
            file = discord.File(fp=myimg, filename='image.png')
            # Send the file with a message
            await ctx.channel.send(file=file)

    @mc.command(name="generate_image_variation",description="make variations of an image")
    async def make_image_var(self,inter:discord.Interaction,image:discord.Attachment,num:int=1,size:Literal['256x256','512x512','1024x1024']='256x256'):
        ctx=await self.bot.get_context(inter)
        await ctx.send("This command is disabled.")
        return
        if not ctx.guild: return
        user_id=ctx.author.id
        targetid,num2=hash.hash_string(str(user_id),hashlen=16,hashset=hash.Hashsets.base64)
        if not 0<num<=10:
            await ctx.send("Invalid number of generations.",ephemeral=True)
            return
        precheck=await precheck_context(ctx)
        if not precheck:
            await ctx.send("Precheck failed.",ephemeral=True)
            return
        mybytes=await image.read()
        byte_stream = io.BytesIO(mybytes)
        img=purgpt.object.ImageVariate(
            image= base64.b64encode(mybytes).decode('utf-8'),
            n=num,
            size=size
        )
        
        message=await ctx.send(f"Generating image{'s' if num>1 else ''}...")
        async with ctx.channel.typing():
            #Call the API.
            result=await ctx.bot.gptapi.callapi(img)
        for data in result.data:
            myimg=await download_image(data['url'])
            # Create a discord.File object using the image_bytes
            file = discord.File(fp=myimg, filename='image.png')
            # Send the file with a message
            await ctx.channel.send(file=file)



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
       
    @commands.command(brief="Turn on OpenAI mode")
    @commands.is_owner()
    async def openai(self,ctx,mode:bool=False):
        '''"Update user or server api limit `[server,user],id,limit`"'''
        self.bot.gptapi.set_openai_mode(mode)
        if mode==True:
            await ctx.send("OpenAI mode turned on.")
        if mode==False:
            await ctx.send("OpenAI mode turned off.")
        
        
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
                await ai_message_invoke(self.bot,message, mylib=self.flib)
            else:
                if profile.has_channel(message.channel.id):
                    await ai_message_invoke(self.bot,message,mylib=self.flib)
        except Exception as error:           
            try:
                emb=MessageTemplates.get_error_embed(title=f"Error with your query!",description=str(error))
                await message.channel.send(embed=emb)
            except Exception as e:
                
                try:
                    myperms= message.guild.system_channel.permissions_for(message.guild.me)
                    if myperms.send_messages:
                        await message.guild.system_channel.send('I need to be able to send messages in a channel to use this feature.')
                except e:
                    pass
                        
                await self.bot.send_error(e,title=f"Could not send message",uselog=True)
            await self.bot.send_error(error,title=f"AI Responce error",uselog=True)

    

    

        


async def setup(bot):
    from .AICalling import setup
    await bot.load_extension(setup.__module__)
    await bot.add_cog(AICog(bot))
async def teardown(bot):
    from .AICalling import setup
    await bot.unload_extension(setup.__module__)
    await bot.remove_cog('AICog')

