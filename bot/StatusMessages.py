import gui
import random
import string
from discord.ext import commands, tasks
import datetime
import asyncio
import discord
from utility import urltomessage

from queue import Queue


class StatusEditMessage:
    """edit a message at a regular interval."""

    def __init__(self, message: discord.Message, ctx: commands.Context):
        self.bot = ctx.bot
        self.message = message
        self.last_update_time = datetime.datetime.now()
        self.initial_deploy_time = datetime.datetime.now()
        self.embed = None
        if message.embeds:
            self.embed = message.embeds[0]

    def check_update_interval(self):
        """get the time between now and the last time updatew was called."""
        time_diff = datetime.datetime.now() - self.last_update_time
        return time_diff.total_seconds()

    def check_totaltime(self):
        """get the time between now and the last time updatew was called."""
        time_diff = datetime.datetime.now() - self.initial_deploy_time
        return time_diff.total_seconds()

    async def editw(self, min_seconds=0, **kwargs):
        """Update status message asyncronously if min_seconds have passed."""
        if self.check_update_interval() > min_seconds and self.message != None:
            try:
                gui.gprint(str(kwargs))
                if "embed" in kwargs:
                    self.embed = kwargs["embed"]
                await self.message.edit(**kwargs)
            except Exception as e:
                gui.gprint(e)
                self.message = urltomessage(self.message.jump_url, self.bot)
            self.last_update_time = datetime.datetime.now()

    async def delete(self):
        await self.message.delete()


class StatusMessage:
    """Represents a Status Message, a quickly updatable message
    to get information on long operations without having to edit."""

    def __init__(self, id, ctx, bot=None):
        self.id = id
        self.ctx = ctx
        self.status_mess = None
        self.bot = bot
        self.last_update_time = datetime.datetime.now()

    def check_update_interval(self):
        """get the time between now and the last time updatew was called."""
        time_diff = datetime.datetime.now() - self.last_update_time
        return time_diff.total_seconds()

    def update(self, updatetext, **kwargs):
        self.bot.statmess.update_status_message(self.id, updatetext, **kwargs)

    async def updatew(self, updatetext, min_seconds=0, **kwargs):
        """Update status message asyncronously."""
        if self.check_update_interval() > min_seconds:
            await self.bot.statmess.update_status_message_wait(
                self.id, updatetext, **kwargs
            )
            self.last_update_time = datetime.datetime.now()

    def delete(self):
        """Delete this status message.  It's job is done."""
        self.bot.statmess.delete_status_message(self.id)


class StatusMessageManager:
    """Stores all status messages."""

    def __init__(self, bot):
        self.bot = bot
        self.statuses = {}

    def genid(self):
        return "".join(
            random.choices(string.ascii_uppercase + string.ascii_lowercase, k=9)
        )

    def get_message_obj(self, sid):
        return self.statuses[sid]

    def add_status_message(self, ctx):
        sid = self.genid()
        status = StatusMessage(sid, ctx, self.bot)
        self.statuses[sid] = status
        return sid

    async def update_status_message_wait(self, sid, updatetext, **kwargs):
        if sid in self.statuses:
            last = self.statuses[sid].status_mess
            if last != None:
                self.bot.schedule_for_deletion(last, 4)

            pid = await self.statuses[sid].ctx.send(updatetext, **kwargs)
            await asyncio.sleep(0.2)
            gui.gprint(pid)
            self.statuses[sid].status_mess = pid

    def update_status_message(self, sid, updatetext, **kwargs):
        if sid in self.statuses:
            last = self.statuses[sid].status_mess
            if last != None:
                self.bot.schedule_for_deletion(last, 4)
            pid = self.bot.schedule_for_post(self.statuses[sid].ctx, updatetext)
            gui.gprint(pid)
            self.statuses[sid].status_mess = pid

    def delete_status_message(self, sid):
        if sid in self.statuses:
            last = self.statuses[sid].status_mess
            if last != None:
                self.bot.schedule_for_deletion(last)
            self.statuses[sid] = None


class StatusMessageMixin:
    psuedomess_dict = {}
    post_schedule = Queue()
    delete_schedule = Queue()

    def schedule_for_post(self, channel, mess):
        """Schedule a message to be posted in channel."""
        dict = {"op": "post", "pid": self.genid(), "ch": channel, "mess": mess}
        self.post_schedule.put(dict)
        return dict["pid"]

    def schedule_for_deletion(self, message, delafter=0):
        """Schedule a message to be deleted later."""
        now = discord.utils.utcnow()
        dictv = {"op": "delete", "m": message, "then": now, "delay": delafter}
        self.delete_schedule.put(dictv)

    async def post_queue_message_int(self):
        if self.post_schedule.empty() == False:
            dict = self.post_schedule.get()
            m = await dict["ch"].send(dict["mess"])
            self.psuedomess_dict[dict["pid"]] = m

    async def delete_queue_message_int(self):
        if self.delete_schedule.empty() == False:
            message = self.delete_schedule.get()
            now = discord.utils.utcnow()
            then = message["then"]
            delay = message["delay"]
            if (now - then).total_seconds() >= delay:
                if type(message["m"]) == str:
                    if message["m"] in self.psuedomess_dict:
                        await self.psuedomess_dict[message["m"]].delete()
                        self.psuedomess_dict[message["m"]] = None
                    else:
                        self.delete_schedule.put(message)
                elif isinstance(message["m"], discord.Message):
                    try:
                        await message["m"].delete()
                    except:
                        try:
                            jumplink = ""
                            if issubclass(
                                type(message["m"]), discord.InteractionMessage
                            ):
                                jumplink = message["m"].jump_url
                            else:
                                jumplink = message["m"].jump_url
                            newm = await urltomessage(jumplink, self)
                            await newm.delete()
                        except Exception as error:
                            await self.send_error(error, "deletion error...")
            else:
                self.delete_schedule.put(message)
