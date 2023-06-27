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
from purgpt.functionlib import *
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

        self.timerloop.start()

    def cog_unload(self):
        self.timerloop.cancel()
    @tasks.loop(seconds=1)
    async def timerloop(self):
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

    @AILibFunction(name='start_timer',description='Start a timer for a certain number of seconds.')
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
        return 'ok'



    

        



async def setup(bot):
    await bot.add_cog(TimerCog(bot))
