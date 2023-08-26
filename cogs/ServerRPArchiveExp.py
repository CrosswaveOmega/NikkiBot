import gui
from typing import Literal
import discord
import asyncio
import csv
#import datetime
from datetime import datetime, timedelta, date, timezone
from sqlalchemy import event

from utility import serverOwner, serverAdmin, seconds_to_time_string, get_time_since_delta, formatutil
from utility import WebhookMessageWrapper as web, urltomessage, ConfirmView, RRuleView
from bot import TCBot, TCGuildTask, Guild_Task_Functions, StatusEditMessage, TC_Cog_Mixin
from random import randint
from discord.ext import commands, tasks

from dateutil.rrule import rrule,rrulestr, WEEKLY, SU, MINUTELY, HOURLY

from discord import app_commands
from discord.app_commands import Choice

from database.database_ai import AuditProfile, ServerAIConfig
from database import ServerArchiveProfile, DatabaseSingleton
from .ArchiveSub import (
do_group,
  collect_server_history,
  check_channel,
  ArchiveContext,
  collect_server_history_lazy,
  setup_lazy_grab,
  lazy_archive,
  LazyContext,
  ChannelSep,
  ArchivedRPMessage,
  MessageTemplates,
  HistoryMakers, 
  ChannelArchiveStatus
) 
from collections import defaultdict
import gptmod
class ToChoice(commands.Converter):
    async def convert(self, ctx, argument):
        if not ctx.interaction:
            print(type(argument))
            if type(argument)==str:
                choice=Choice(name="fallback",value=argument)
                return choice
        else:
            return argument

class ServerRPArchiveExtra(commands.Cog, TC_Cog_Mixin):
    """This class is intended for Discord RP servers that use Tupperbox or another proxy application.."""
    def __init__(self, bot):
        self.bot:TCBot=bot
        self.loadlock=asyncio.Lock()
        self.helptext= \
        """Extra commands for server archiving.
        """

    def cog_unload(self):
        #Remove the task function.
        pass
    
    @commands.command( extras={"guildtask":['rp_history']})
    async def summarize_day(self, ctx, daystr:str, endstr:str=None):
        """Create a calendar of all archived messages with dates in this channel."""
        bot = ctx.bot
        channel = ctx.message.channel
        guild=channel.guild
        guildid=guild.id
        if await ctx.bot.gptapi.check_oai(ctx):
            return

        serverrep,userrep=AuditProfile.get_or_new(guild,ctx.author)
        userrep.checktime()
        ok, reason=userrep.check_if_ok()
        if not ok:
            if reason in ['messagelimit','ban']:
                await ctx.send("I can not process your request.")
                return
        serverrep.modify_status()
        userrep.modify_status()
        profile=ServerArchiveProfile.get_or_new(guildid)
        

        if profile.history_channel_id == 0:
            await MessageTemplates.get_server_archive_embed(ctx,"Set a history channel first.")
            return False
        if channel.id==profile.history_channel_id:
            return False
        archive_channel=guild.get_channel(profile.history_channel_id)
        if archive_channel==None:
            await MessageTemplates.get_server_archive_embed(ctx,"I can't seem to access the history channel, it's gone!")
            return False
        def format_location_name(csep):
            # Replace dashes with spaces
            channel_name=csep.channel
            category=csep.category
            thread=csep.thread
            formatted_name = channel_name.replace('-', ' ')

            # Capitalize the first letter
            formatted_name = formatted_name.capitalize()
            output=f"Location: {formatted_name}, {category}."
            if thread!=None:
                output=f"{output}  {thread}"
            return output
   
        me=await ctx.channel.send(content=f"<a:LetWalk:1118184074239021209> Retrieving archived messages...")
        mt=StatusEditMessage(me,ctx)
        datetime_object = datetime.strptime(f"{daystr} 00:00:00 +0000",'%Y-%m-%d %H:%M:%S %z')
        datetime_object_end=datetime_object
        if endstr:
            datetime_object_end = datetime.strptime(f"{endstr} 00:00:00 +0000",'%Y-%m-%d %H:%M:%S %z')
        se=ChannelSep.get_all_separators_on_date(guildid,datetime_object)
        prompt='''
        You are to summarize a series of chat logs sent across a period of time.
        The log is broken up into segments that start with a message indicating where the conversation took place in, of format:
        'Location: [location name], [location category].  [Optional Sub location].'
        Each message is of format:
        '[character name]: [ContentHere]'
        The Summary's length must reflect the length of the chat log.  A minimum of 2 paragraphs with 5-10 sentences each is required.  
        You must not make overgeneralizations.  You should extract as much key detail as possible while keeping it consise.
        '''
        def get_seps_between_dates(start,end):
            '''this generator returns lists of all separators that are on the specified dates.'''
            cd = start
            print('starting')
            while cd <= end:   
                dc=0
                print(cd)
                se=ChannelSep.get_all_separators_on_date(guildid,cd)
                if se:
                    yield se
                cd += timedelta(days=1)

        script=''''''
        count=ecount=mcount=0
        ecount=0
        await ctx.send('Starting gather.')

        for sep in ChannelSep.get_all_separators_on_dates(guildid, datetime_object,datetime_object_end):
            ecount+=1
            tokens=gptmod.util.num_tokens_from_messages([
                {'role':'system','content':prompt},{
                    'role':'user','content':script}],'gpt-3.5-turbo-16k')
            await mt.editw(min_seconds=15,content=f"<a:LetWalk:1118184074239021209> Currently on Separator {ecount} ({sep.message_count}),message {mcount}.  Tokensize is {tokens}")
            location=format_location_name(sep)
            if tokens> 16384:
                await ctx.send("I'm sorry, but there's too much content on this day for me to summarize.")
                return
            script+="\n"+location+'\n'
            await asyncio.sleep(0.2)
            messages=sep.get_messages()
            await asyncio.sleep(0.5)
            for m in messages:
                count+=1
                mcount+=1
                await asyncio.sleep(0.1)
                if count>5:
                    #To avoid blocking the asyncio loop.
                    
                    tokens=gptmod.util.num_tokens_from_messages([
                    {'role':'system','content':prompt},{
                        'role':'user','content':script}],'gpt-3.5-turbo-16k')
                    await mt.editw(min_seconds=15,content=f"<a:LetWalk:1118184074239021209> Currently on Separator {ecount},message {mcount}.  Tokensize is {tokens}")
                    if tokens> 16384:
                        await ctx.send("I'm sorry, but there's too much content on this day for me to summarize.")
                        return
                    count=0
                embed=m.get_embed()
                if m.content:
                    script=f"{script}\n {m.author}: {m.content}"
                elif embed:
                    embed=embed[0]
                    if embed.type=='rich':
                        embedscript=f"{embed.title}: {embed.description}"
                        script=f"{script}\n {m.author}: {embedscript}"
        chat=gptmod.ChatCreation(
                messages=[{'role': "system", 'content':  prompt }],
                model='gpt-3.5-turbo-16k'
            )
        gui.gprint(script)

        chat.add_message(role='user',content=script)
        tokens=gptmod.util.num_tokens_from_messages(chat.messages,'gpt-3.5-turbo-16k')
        await ctx.send(tokens)
        if tokens> 16384:
            await ctx.send("I'm sorry, but there's too much content on this day for me to summarize.")
            return
        #Call API
        bot=ctx.bot
        messageresp=None

        async with ctx.channel.typing():

            res=await bot.gptapi.callapi(chat)

            #await ctx.send(res)
            print(res)
            if res.get('error',False):
                err=res['error']
                error=gptmod.error.GptmodError(err,json_body=res)
                raise error
            if res.get('err',False):
                err=res[err]
                error=gptmod.error.GptmodError(err,json_body=res)
                raise error
            result=res['choices'][0]['message']['content']
            page=commands.Paginator(prefix='',suffix=None,max_size=4000)
            for p in result.split("\n"):
                page.add_line(p)
            messageresp=None
            for pa in page.pages:
                embed=discord.Embed(
                    title='summary',
                    description=pa[:4028]
                )
                ms=await ctx.channel.send(embed=embed)
                
                if messageresp==None:messageresp=ms
        



async def setup(bot):
    print(__name__)
    #from .ArchiveSub import setup
    #await bot.load_extension(setup.__module__)
    await bot.add_cog(ServerRPArchiveExtra(bot))



async def teardown(bot):
    #from .ArchiveSub import setup
    #await bot.unload_extension(setup.__module__)
    await bot.remove_cog('ServerRPArchiveExtra')
