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
from utility import MessageTemplates, RRuleView, formatutil, seconds_to_time_string
from utility.embed_paginator import pages_of_embeds
from bot import TCBot,TC_Cog_Mixin, super_context_menu
import purgpt
from database import DatabaseSingleton
from purgpt.functionlib import *
import purgpt.error
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
import gui


Base = declarative_base()


class TimerTable(Base):
    __tablename__ = 'timer_table'

    user_id = Column(Integer, primary_key=True)
    name = Column(String, primary_key=True)
    invoke_on = Column(DateTime)

    @staticmethod
    def add_timer(user_id, name, trigger_on):
        session=DatabaseSingleton.get_session()
        new_timer = TimerTable(user_id=user_id, name=name, invoke_on=trigger_on)
        session.add(new_timer)
        session.commit()

    @staticmethod
    def get_timer(user_id, name):
        session=DatabaseSingleton.get_session()
        timer = session.query(TimerTable).filter_by(user_id=user_id, name=name).first()
        if timer:
            time_diff = timer.invoke_on - datetime.now()
            return time_diff.total_seconds() if time_diff.total_seconds() > 0 else 0
        else:
            return None

    @staticmethod
    def get_expired_timers():
        session=DatabaseSingleton.get_session()
        expired_timers = session.query(TimerTable).filter(TimerTable.invoke_on < datetime.now()).all()
        return expired_timers

    @staticmethod
    def remove_expired_timers():
        session=DatabaseSingleton.get_session()
        expired_timers = TimerTable.get_expired_timers(session)
        for timer in expired_timers:
            session.delete(timer)
        session.commit()
    
class TimerCog(commands.Cog, TC_Cog_Mixin):
    """For Timers."""
    def __init__(self, bot):
        self.helptext=""
        self.bot=bot
        self.init_context_menus()

        self.timerloop.start()

    def cog_unload(self):
        self.timerloop.cancel()
    @tasks.loop(seconds=1)
    async def timerloop(self):
        try:
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
        await ctx.send(comment)
        await ctx.send(f"Timer {name} is set for <t:{target.timestamp()}:R>")
        return 'ok'



    

        



async def setup(bot):
    await bot.add_cog(TimerCog(bot))
