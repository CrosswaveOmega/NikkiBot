import random
import string
from discord.ext import commands, tasks
import datetime
import asyncio

class StatusMessage:
    '''Represents a Status Message, a quickly updatable message 
    to get information on long operations without having to edit.'''
    def __init__(self,id,ctx,bot=None):
        self.id=id
        self.ctx=ctx
        self.status_mess=None
        self.bot=bot
        self.last_update_time=datetime.datetime.now()
    def check_update_interval(self):
        '''get the time between now and the last time updatew was called.'''
        time_diff = datetime.datetime.now() - self.last_update_time
        return time_diff.total_seconds()
    def update(self,updatetext,**kwargs):
        self.bot.statmess.update_status_message(self.id,updatetext,**kwargs)
    async def updatew(self,updatetext, min_seconds=0, **kwargs):
        '''Update status message asyncronously.'''
        if self.check_update_interval()>min_seconds:
            await self.bot.statmess.update_status_message_wait(self.id,updatetext, **kwargs)
            self.last_update_time=datetime.datetime.now()
    def delete(self):
        '''Delete this status message.  It's job is done.'''
        self.bot.statmess.delete_status_message(self.id)

class StatusMessageManager:
    '''Stores all status messages.'''
    def __init__(self, bot):
        self.bot=bot
        self.statuses={}
    def genid(self):
        return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=9))
    def get_message_obj(self,sid):
        return self.statuses[sid]
    def add_status_message(self, ctx):
        sid=self.genid()
        status=StatusMessage(sid,ctx,self.bot)
        self.statuses[sid]=status
        return sid
    async def update_status_message_wait(self,sid,updatetext,**kwargs):
        if sid in self.statuses:
            last=self.statuses[sid].status_mess
            if last!=None:
              self.bot.schedule_for_deletion(last,4)
            
            pid=await self.statuses[sid].ctx.send(updatetext,**kwargs)
            await asyncio.sleep(0.2)
            print(pid)
            self.statuses[sid].status_mess=pid
    def update_status_message(self, sid, updatetext,**kwargs):
        if sid in self.statuses:
            last=self.statuses[sid].status_mess
            if last!=None:
              self.bot.schedule_for_deletion(last,4)
            pid=self.bot.schedule_for_post(self.statuses[sid].ctx,updatetext)
            print(pid)
            self.statuses[sid].status_mess=pid
    def delete_status_message(self,sid):
        if sid in self.statuses:
            last=self.statuses[sid].status_mess
            if last!=None:
              self.bot.schedule_for_deletion(last)
            self.statuses[sid]=None
