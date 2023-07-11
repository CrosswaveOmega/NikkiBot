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
from utility import MessageTemplates, RRuleView, formatutil, seconds_to_time_string, urltomessage
from utility.embed_paginator import pages_of_embeds
from bot import TCBot,TC_Cog_Mixin, super_context_menu
import purgpt
from database import DatabaseSingleton
from gptfunctionutil import *
import purgpt.error
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
import gui


Base = declarative_base(name='Timer Base')

#Also for testing DatabaseSingleton's asyncronous mode.

class TimerTable(Base):
    __tablename__ = 'timer_table'

    user_id = Column(Integer, primary_key=True)
    name = Column(String, primary_key=True)
    message_url = Column(String,nullable=True)
    invoke_on = Column(DateTime)

    @staticmethod
    async def add_timer(user_id, name, trigger_on, url):
        async with await DatabaseSingleton.get_async_session() as session:
            new_timer = TimerTable(user_id=user_id, name=name, invoke_on=trigger_on,message_url=url)
            session.add(new_timer)
            await session.commit()
            return new_timer

    @staticmethod
    async def get_timer(user_id, name):
        async with await DatabaseSingleton.get_async_session() as session:
            timer = await session.execute(select(TimerTable).filter_by(user_id=user_id, name=name))
            timer = timer.scalar_one_or_none()
            if timer:
                time_diff = timer.invoke_on - datetime.now()
                return time_diff.total_seconds() if time_diff.total_seconds() > 0 else 0
            else:
                return None

    @staticmethod
    async def get_expired_timers():
        async with await DatabaseSingleton.get_async_session() as session:
            expired_timers = await session.execute(select(TimerTable).filter(TimerTable.invoke_on < datetime.now()))
            return expired_timers.scalars().all()

    @staticmethod
    async def remove_expired_timers():
        async with await DatabaseSingleton.get_async_session() as session:
            expired_timers_query = await session.execute(select(TimerTable).filter(TimerTable.invoke_on < datetime.now()))
            expired_timers= expired_timers_query.scalars().all()
            for timer in expired_timers:
                print('attempting to remove: timer')
                await session.delete(timer)
            await session.commit()

    @staticmethod
    async def list_timers(user_id):
        async with await DatabaseSingleton.get_async_session() as session:
            timers = await session.execute(select(TimerTable).where(TimerTable.user_id == user_id))
            return timers.scalars().all()

    def __str__(self):
        return f"Timer: **{self.name}**, in <t:{int(self.invoke_on.timestamp())}:R>, on {self.message_url}"

    
    
class TimerCog(commands.Cog, TC_Cog_Mixin):
    """For Timers."""
    def __init__(self, bot):
        self.helptext=""
        self.bot=bot
        bot.database.load_base(Base)
        self.countdown=200
        self.timerloop.start()

    def cog_unload(self):
        self.timerloop.cancel()
    @tasks.loop(seconds=1)
    async def timerloop(self):
        if self.countdown>0:
            self.countdown-=1
            return
        try:
            async with await DatabaseSingleton.get_async_session() as session:
                expired=await TimerTable.get_expired_timers()
                if expired:
                    for t in expired:
                        message=await urltomessage(t.message_url,bot=self.bot)
                        if message:
                            await message.reply(f"<@{t.user_id}>, Your {t.name} timer is done.")
                        else:
                            try:
                                use=self.bot.get_user(t.user_id)
                                await use.send(f"<@{t.user_id}>, Your {t.name} timer is done.")
                            except:
                                gui.gprint("can't reach user.")
                        await session.delete(t)
                    await session.commit()
                    await session.flush()
                    await TimerTable.remove_expired_timers()
                else:
                    pass
        except Exception as e:
            await self.bot.send_error(e, f"Timerloop")
            gui.gprint(str(e))
    @AILibFunction(name='alarm',description='Set a one time alarm for a future date and time.', required=['comment'])
    @LibParam(comment='An interesting, amusing remark.',name='The name of the alarm to use',alarm_time='Datetime of the alarm to use in UTC.')
    @commands.command(name='start_alarm',description='Set a one time alarm.',extras={})
    async def start_alarm(self,ctx:commands.Context,name:str,alarm_time:datetime,comment:str="Alarm set."):
        #This is an example of a decorated discord.py command.
        bot=ctx.bot
        now=datetime.now()
        preexist=await TimerTable.get_timer(ctx.author.id,name)
        if preexist:
            await ctx.send("There already is a alarm by that name!")
            return
        message=ctx.message
        print(message.jump_url)
        target_message=await ctx.send(f"{comment}\nTimer {name} is set for <t:{int(alarm_time.timestamp())}:R>")
        timer=await TimerTable.add_timer(ctx.author.id,name,alarm_time,message.jump_url)
        
        timer.message_url=target_message.jump_url
        async with await DatabaseSingleton.get_async_session() as session:
            await session.commit()
        return target_message
    @AILibFunction(name='start_timer',description='Start a timer for a certain number of seconds.', required=['set a timer','start a timer', 'timer for', 'start timer'])
    @LibParam(comment='An interesting, amusing remark.',name='The name of the timer to use',total_seconds='the total amount of seconds the timer will run for.')
    @commands.command(name='start_timer',description='Get the current UTC Time',extras={})
    async def start_timer(self,ctx:commands.Context,comment:str,name:str,total_seconds:int):
        #This is an example of a decorated discord.py command.
        bot=ctx.bot
        now=datetime.now()
        target=now + timedelta(seconds=float(total_seconds))
        preexist=await TimerTable.get_timer(ctx.author.id,name)
        if preexist:
            await ctx.send("There already is a timer by that name!")
            return
        message=ctx.message
        print(message.jump_url)
        target_message=await ctx.send(f"{comment}\nTimer {name} is set for <t:{int(target.timestamp())}:R>")
        timer=await TimerTable.add_timer(ctx.author.id,name,target,message.jump_url)
        
        timer.message_url=target_message.jump_url
        async with await DatabaseSingleton.get_async_session() as session:
            await session.commit()
        return target_message
    @AILibFunction(name='view_timers',description='View all currently active timers.')
    @LibParam(comment='An interesting, amusing remark.')
    @commands.command(name='timer_view',description="View all timers you've made.",extras={})
    async def showtimers(self,ctx:commands.Context,comment:str):
        #This is an example of a decorated discord.py command.
        bot=ctx.bot
        invoker=ctx.author.id
        now=datetime.now()
        mytimers=await TimerTable.list_timers(invoker)
        if mytimers:
            page=commands.Paginator(prefix='',suffix=None)
            page.add_line(comment)
            for timer in mytimers:
                page.add_line(str(timer))
            messageresp=None
            for pa in page.pages:
                ms=await ctx.channel.send(pa)
                if messageresp==None:
                    messageresp=ms
            
            return messageresp
        else:
            return await ctx.send("You don't have any timers.")
        
    @AILibFunction(
        name='event_schedule',
        description="Create a scheduled server event at a certain date,time, and with a name and description.",
        required=['end_time','description']
    )
    @LibParam(
        name='The name of the event to schedule.',
        start_time='datetime to start the event at, in UTC.',
        end_time='datetime to end the event at, in UTC.',
        channelname='the name of the voice channel the event will occur within.  This is usually denoted as <#{integer}> in a user prompt.',
        description='The description of what the event is.'
    )
    @commands.command(name='event_schedule',description='schedule an event.',extras={}) #Command decorator.
    @commands.guild_only()
    async def schedule_event(
            self, ctx:commands.Context, 
            name: str, 
            end_time: datetime,
            start_time: datetime, 
            channelname: str,
            description: str = 'default description'
        ):
        channel:discord.VoiceChannel= discord.utils.get(ctx.guild.channels, name=channelname.replace("#",""))
        # Permission check
        if not ctx.author.guild_permissions.manage_events:
            return await ctx.send('You do not have permission to create scheduled events.')
        if not ctx.guild.me.guild_permissions.manage_events:
            return await ctx.send("I do not have permission to create scheduled events.")
        
        image=await ctx.guild.icon.read()
        # Create the scheduled event
        event = await ctx.guild.create_scheduled_event(
            name=name, start_time=start_time, 
            channel=channel, 
            end_time=end_time, description=description,
            privacy_level=discord.PrivacyLevel.guild_only,
            image=image
        )

        mes=await ctx.send(f'Scheduled event "{event.name}" created!')
        return mes


    

        



async def setup(bot):
    await bot.add_cog(TimerCog(bot))
