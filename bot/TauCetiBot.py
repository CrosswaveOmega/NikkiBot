from typing import Any
import discord
import traceback
import asyncio

import logging
import logging.handlers
import os

from queue import Queue
from discord.ext import commands, tasks

import random
import string
from database import *

from utility import Chelp, urltomessage, MessageTemplates

""" Primary Class

This file is for an extended Bot Class for this Discord Bot.

The Notebook is a singleton design pattern that this bot uses to store any
persistent data that can be accessed anywhere within the bot's extensions,
directly from the passed in bot instance.

Any data saved within the Notebook is recorded within the saveData directory initalized
upon first startup.

The Notebook's data entries are split amoung instances of the NotebookPage class,
an object with a to_dictionary object intended to save the Instances components into a dictionary
that can be encoded into a readable JSON file.


"""

intent=discord.Intents.default();
intent.presences=True
intent.message_content=True
intent.guilds=True
intent.members=True
from database import DatabaseSingleton

class StatusMessage:
    '''Represents a Status Message, a quickly updatable message 
    to get information on long operations without having to edit.'''
    def __init__(self,id,ctx,bot=None):
        self.id=id
        self.ctx=ctx
        self.status_mess=None
        self.bot=bot
    def update(self,updatetext,**kwargs):
        self.bot.statmess.update_status_message(self.id,updatetext,**kwargs)
    async def updatew(self,updatetext, **kwargs):
        '''Update status message code.'''
        await self.bot.statmess.update_status_message_wait(self.id,updatetext, **kwargs)
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

class TCBot(commands.Bot):
    
    """TC's central bot class.  An extension of discord.py Bot class with additional functionality."""
    def __init__(self):
        super().__init__(command_prefix=['tauceti_>',">"], help_command=Chelp(), intents=intent)

        self.database=DatabaseSingleton("Startup")

        
        self.statmess:StatusMessageManager=StatusMessageManager(self)

        self.logs=logging.getLogger("TCLogger")
        self.loggersetup()

        self.extensiondir,self.extension_list="",[]
        self.plugindir,self.plugin_list="",[]
        self.psuedomess_dict= {}
        self.loaded_extensions={}
        self.loaded_plugins={}
       
        self.post_schedule=Queue()
        self.delete_schedule=Queue()
        self.default_error=self.on_command_error
    async def on_close(self):
        # Close the SQLAlchemy engine
        self.database.close_out()

        # Logout the bot from Discord
        await self.logout()
    def loggersetup(self):
        self.logs.setLevel(logging.INFO)
        handler = logging.handlers.RotatingFileHandler(
            filename='./logs/tauceti__log.log',
            encoding='utf-8',
            maxBytes=32 * 1024 * 1024,  # 32 MiB
            backupCount=5,  # Rotate through 5 files
        )
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        formatter = logging.Formatter('[LINE] [{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
        handler.setFormatter(formatter)
        self.logs.addHandler(handler)

    def set_ext_directory(self, dir:str):
        self.extensiondir=dir

    

    def update_ext_list(self):
        '''Update the internal exension list.'''
        self.extension_list=[]
        for filename in os.listdir(self.extensiondir):
            print(filename)
            if filename.endswith('.py'):
                extensionname=f'cogs.{filename[:-3]}'
                print(extensionname)
                self.extension_list.append(extensionname)


    def add_status_message(self,ctx)->StatusMessage:
        '''return a status message object'''
        cid=self.statmess.add_status_message(ctx)
        return self.statmess.get_message_obj(cid)

    async def sync_enabled_cogs_for_guild(self,guild):
        '''With a passed in guild, sync all activated cogs.'''        
        def syncprint(lis):
            print(f"Sync for {guild.name} (ID {guild.id})",lis)
        for cogname, cog in self.cogs.items():
            syncprint(cogname)
            enabled=True
            if cogname=="Setup": #Setup shouldn't 
                enabled=False
            if enabled:
                for x in cog.walk_commands():
                    if isinstance(x, (commands.HybridCommand, commands.HybridGroup)):
                        try:
                            self.tree.add_command(x.app_command,guild=guild, override=True)
                            syncprint(f"Added hybrid{x.name}")
                        except:
                            syncprint(f"...can't add {x.name}")
                        syncprint(f"Norm {x.name}")
                for x in cog.walk_app_commands():
                    try:
                        self.tree.add_command(x,guild=guild, override=True)
                        syncprint(f"Added AppCommand  {x.name}")
                    except:
                        syncprint(f"can't add {x.name}")
        syncprint("Syncing...")
        await self.tree.sync(guild=guild)

    async def all_guild_startup(self):
        
        async for guild in self.fetch_guilds(limit=10000):
            print(f"syncing for {guild.name}")
            await self.sync_enabled_cogs_for_guild(guild)

    async def reload_all(self):
        

        for i, e in self.loaded_extensions.items():
            if not i in self.extension_list:
                await self.unload_extension(i)
                self.loaded_extensions[i]=None

        for ext in self.extension_list:
            if not ext in self.loaded_extensions: await self.extension_loader(ext)
            else: 
                val=await self.extension_reload(ext)


        print(self.extension_list)

    def genid(self):
        return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=9))
    def pswitchload(self,pmode=False):
        return self.loaded_extensions

    async def extension_loader(self,extname,plugin=False):
        """Load an extension and add it to the internal loaded extension dictionary."""
        
        print("LOADING", extname)
        self.pswitchload(plugin)[extname]=("settingup",None)
        try:
            print("LOADING", extname)
            await self.load_extension(extname)
            self.pswitchload(plugin)[extname]=("running",None)
            return "LOADOK"
        except Exception as ex:
            en=str(ex)
            print(en)
            tracebackstr=''.join(traceback.format_exception(None, ex, ex.__traceback__))
            self.pswitchload(plugin)[extname]=(en,tracebackstr)
            return tracebackstr

    async def extension_reload(self,extname,plugin=False):
        '''reload an extension by EXTNAME.  '''
        if not extname in self.pswitchload(plugin): return "NOTFOUND"
        if extname in self.pswitchload(plugin):
            self.pswitchload(plugin)[extname]=("settingup",None)
            try:
                await self.reload_extension(extname)
                self.pswitchload(plugin)[extname]=("running",None)
                return "RELOADOK"
            except commands.ExtensionNotLoaded as ex:
                return await self.extension_loader(extname)
            except Exception as ex:
                en=str(ex)
                tracebackstr=''.join(traceback.format_exception(None, ex, ex.__traceback__))
                self.pswitchload(plugin)[extname]=(en,tracebackstr)
                return tracebackstr



    def schedule_for_post(self,channel,mess):
        """Schedule a message to be posted in channel."""
        dict={"op":'post',"pid":self.genid(),"ch":channel,"mess":mess}
        self.post_schedule.put(dict)
        return dict["pid"]
        
    def schedule_for_deletion(self, message, delafter=0):
        """Schedule a message to be deleted later."""
        now=discord.utils.utcnow()

        dictv={"op":'delete',"m":message,"then":now,"delay":delafter}
        self.delete_schedule.put(dictv)






    async def send_error_embed(self,emb=None,content=None):
        '''send error embed to debug channel.'''
        chan=self.get_channel(1042518240708018207)
        await chan.send(content=content,embed=emb)
        
    async def send_error(self,error,title):
        just_the_string=''.join(traceback.format_exception(None, error, error.__traceback__))
        er=MessageTemplates.get_error_embed(title=f"Error with {title}",description=f"{just_the_string},{str(error)}")
        er.add_field(name="Details",value=f"{title},{error}")
        await self.send_error_embed(er)



    @tasks.loop(seconds=1.0)
    async def post_queue_message(self):
        if self.post_schedule.empty()==False:
            dict=self.post_schedule.get()
            m=await dict["ch"].send(dict["mess"])
            self.psuedomess_dict[dict["pid"]]=m

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        '''internal command logger.'''
        log=logging.getLogger('discord')
        
        command :discord.ext.commands.command = ctx.command
        log.error('Ignoring exception in command %s', command, exc_info=error)
        emb=MessageTemplates.get_error_embed(title=f"Error with {ctx.message.content}",description=f"{str(error)}")
        
        just_the_string=''.join(traceback.format_exception(None, error, error.__traceback__))
        er=MessageTemplates.get_error_embed(title=f"Error with {ctx.message.content}",description=f"{just_the_string},{str(error)}")
        er.add_field(name="Details",value=f"{ctx.message.content},{error}")
        await ctx.send(embed=emb)
        await self.send_error_embed(er)

        
    @tasks.loop(seconds=1.0)
    async def delete_queue_message(self):
        if self.delete_schedule.empty()==False:
            message=self.delete_schedule.get()
            now=discord.utils.utcnow()
            then=message["then"]
            delay=message["delay"]
            if (now-then).total_seconds()>=delay:
                if type(message["m"])==str:
                    if message["m"] in self.psuedomess_dict:
                        await self.psuedomess_dict[message["m"]].delete()
                        self.psuedomess_dict[message["m"]]=None
                    else:
                        self.delete_schedule.put(message)
                elif isinstance(message["m"],discord.Message):
                    try:
                        await message["m"].delete()
                    except:
                        try:
                            jumplink=""
                            if issubclass(type(message["m"]),discord.InteractionMessage):
                                jumplink=message["m"].jump_url
                            else:
                                jumplink=message["m"].url
                            newm=await urltomessage(jumplink,self)
                            await newm.delete()
                        except Exception as error:
                            await self.send_error(error, "deletion error...")
                            

            else:
                self.delete_schedule.put(message)

        
