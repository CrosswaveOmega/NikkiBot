from typing import Any, List
import discord
import traceback
import asyncio

import logging
import logging.handlers
import os

from discord.ext import commands, tasks
import datetime
import random
import string
from assets import AssetLookup
from database import *
from .Tasks.TCTasks import TCTaskManager
from sqlalchemy.exc import IntegrityError
import gui
from utility import Chelp, urltomessage, MessageTemplates, replace_working_directory
from .TcGuildTaskDB import Guild_Task_Base, Guild_Task_Functions, TCGuildTask
from .TCAppCommandAutoSync import(
    Guild_Sync_Base, AppGuildTreeSync,
    build_and_format_app_commands, SpecialAppSync
    )
from .TCMixins import CogFieldList, StatusTicker
""" Primary Class

This file is for an extended Bot Class for this Discord Bot.


"""

intent=discord.Intents.default();
intent.presences=True
intent.message_content=True
intent.guilds=True
intent.members=True
from database import DatabaseSingleton, Users_DoNotTrack
from .StatusMessages import StatusMessageManager, StatusMessage, StatusMessageMixin
from .PlaywrightAPI import PlaywrightMixin
from discord import Interaction
from discord.app_commands import CommandTree
import gui

class TreeOverride(CommandTree):
    #I need to do this just to get a global check on app_commands...
    async def interaction_check(self, interaction: Interaction) -> bool:
      '''Don't fire if the user wants to be ignored, but ensure that the user can
      unignore themselves later.'''
      if interaction.command:
          if interaction.command.extras:
              if 'nocheck' in interaction.command.extras:
                  return True
      uid=interaction.user.id
      if Users_DoNotTrack.check_entry(uid):
          return False
      return True

    async def _call(self, interaction: Interaction):
        #because there's no global before invoke for app commands.
        if not await self.interaction_check(interaction):
            interaction.command_failed = True
            return
        if interaction.command:
            gui.gprint("app command call: ",interaction.command.name)
        await super()._call(interaction)


class TCBot(commands.Bot, CogFieldList,StatusTicker,StatusMessageMixin, SpecialAppSync,PlaywrightMixin):
    """A new central bot class.  An extension of discord.py's Bot class with additional functionality."""
    def __init__(self, guimode=False):
        super().__init__(command_prefix=['tc>',">"], tree_cls=TreeOverride,help_command=Chelp(), intents=intent)
        #The Database Singleton is initalized in here.
        self.database=None

        
        self.error_channel=None

        self.statmess:StatusMessageManager=StatusMessageManager(self)

        self.logs=logging.getLogger("TCLogger")
        self.loggersetup()

        self.extensiondir,self.extension_list="",[]
        self.plugindir,self.plugin_list="",[]
        self.guimode=guimode
        self.gui=None
        if guimode:
            self.gui=gui.Gui()
        self.loaded_extensions={}
        self.loaded_plugins={}
        self.default_error=self.on_command_error
        self.bot_ready=False

    def database_on(self):
        '''turn the database on.'''
        self.database= DatabaseSingleton("Startup")
        self.database.load_base(Base=Guild_Task_Base)
        self.database.load_base(Base=Guild_Sync_Base)
        self.database.startup()


    def set_error_channel(self,newid):
        '''set the error channel id.'''
        if str(newid).isdigit():
            self.error_channel=int(newid)
            return True
        return False

    async def after_startup(self):
        '''This function is called in on_ready, but only once.'''
        if not self.bot_ready:
            #if self.guimode:   self.gui.run(self.loop) #update_every_second()
            if self.guimode:
                self.gui.run(self.loop)
                pass
                #self.gthread=gui.Gui.run(self.gui)
            self.database_on()
            self.update_ext_list()
            await self.reload_all()

            #audit old guild data.
            await self.audit_guilds()

            await self.all_guild_startup()
            gui.gprint("BOT SYNCED!")
            self.delete_queue_message.start()
            self.post_queue_message.start()
            self.status_ticker.start()
            for g in self.guilds:
                mytasks=TCGuildTask.get_tasks_by_server_id(g.id)
                for t in mytasks:
                    t.to_task(self)
            self.bot_ready=True
            dbcheck=self.database.database_check()
            gui.gprint(dbcheck)
            await self.start_player()
            now = datetime.datetime.now()
            seconds_until_next_minute = (60 - now.second)%20
            gui.gprint('sleeping for ',seconds_until_next_minute)
            await asyncio.sleep(seconds_until_next_minute)
            self.check_tc_tasks.start()
            # Start the coroutine

    async def close(self):
        print("Signing off.")
        # Close the SQLAlchemy engine
        self.database.close_out()
        # Logout the bot from Discord
        self.post_queue_message.cancel()
        self.delete_queue_message.cancel()
        self.check_tc_tasks.cancel()
        self.status_ticker.cancel()

            
        if self.gui:  
            await self.gui.kill()
        if self.playapi:
            try:
                try:  await asyncio.wait_for(self.close_browser(), timeout=8)
                except Exception as ex:
                    print('rt',ex)
                print("done closing.")
                self.playapi.stop()
                print()
            except Exception as e:
                #l=logging.getLogger("TCLogger")
                self.logs.error('here',str(e))
        print("close done?")
            
        await super().close()

    def loggersetup(self):
        '''Setup the loggers.'''
        if not os.path.exists('./logs/'):
            os.makedirs('./logs/')
        handler2 = logging.handlers.RotatingFileHandler(
            filename='./logs/discord.log',
            encoding='utf-8',
            maxBytes=7 * 1024 * 1024,  # 32 MiB
            backupCount=5,  # Rotate through 5 files
        )
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        formatter2 = logging.Formatter('[LINE] [{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
        handler2.setFormatter(formatter2)
        discord.utils.setup_logging(level=logging.INFO,handler=handler2,root=False)
        #SQLALCHEMY LOGGER.
        sqlalchemy_logger = logging.getLogger('sqlalchemy.engine')
        sqlalchemy_logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler("./logs/sqlalchemy.log"
            ,encoding='utf-8'
        )
        sqlalchemy_logger.addHandler(file_handler)
        #Sqlalchemylogger.
        
        self.logs=logging.getLogger("TCLogger")
        self.logs.setLevel(logging.INFO)
        handlerTC = logging.handlers.RotatingFileHandler(
            filename='./logs/tauceti__log.log',
            encoding='utf-8',
            maxBytes=32 * 1024 * 1024,  # 32 MiB
            backupCount=5,  # Rotate through 5 files
        )
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        formatter4 = logging.Formatter('[LINE] [{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
        handlerTC.setFormatter(formatter4)
        self.logs.addHandler(handlerTC)
        zehttp=logging.getLogger('discord.http')
        zehttp.setLevel(logging.INFO)
        handler = logging.handlers.RotatingFileHandler(
            filename='./logs/discord_http.log',
            encoding='utf-8',
            maxBytes=32 * 1024 * 1024,  # 32 MiB
            backupCount=5,  # Rotate through 5 files
        )
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        formatter = logging.Formatter('[LINE] [{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
        handler.setFormatter(formatter)
        zehttp.addHandler(handler)

    def set_ext_directory(self, dir:str):
        self.extensiondir=dir

    def update_ext_list(self):
        '''Update the internal exension list.'''
        self.extension_list=[]
        for filename in os.listdir(self.extensiondir):
            gui.gprint(filename)
            if filename.endswith('.py'):
                extensionname=f'cogs.{filename[:-3]}'
                gui.gprint(extensionname)
                self.extension_list.append(extensionname)


    def add_status_message(self,ctx)->StatusMessage:
        '''return a status message object'''
        cid=self.statmess.add_status_message(ctx)
        return self.statmess.get_message_obj(cid)
    

    async def audit_guilds(self,override_for:int=None):
        '''audit guilds.'''
        metadata=self.database.get_metadata()
        matching_tables = []
        matching_tables_2 =[]
        for table_name in metadata.tables.keys():
            table = metadata.tables[table_name]
            if 'server_id' in table.columns.keys():
                matching_tables.append((table_name,table))
            if 'server_profile_id' in table.columns.keys():
                matching_tables_2.append((table_name,table))

        # gui.gprint the tables found with matching column name
        gui.gprint(", ".join( f[0] for f in matching_tables))
        
        guilds_im_in=[]
        for guild in self.guilds:
            gui.gprint(guild.id,override_for)
            if guild.id!=override_for:
                guilds_im_in.append(guild.id)
        audit_results=ServerData.Audit(guilds_im_in)
        to_purge=[auditme.server_id for auditme in audit_results]
        self.logs.info(audit_results)
        session=self.database.get_session()
        for server_id_val in to_purge:
            try:
                for tab in matching_tables:
                    table_name,table_obj=tab
                    # loop over the table names and delete the entries
                    count=session.query(table_obj).filter_by(server_id=server_id_val).count()
                    self.logs.info(f"Purging in {table_name}, {server_id_val}.  {count} entries will be removed.")
                    
                    # Delete the records from the table where server_id equals X
                    session.query(table_obj).filter_by(server_id=server_id_val).delete()
                    session.commit()
                    self.logs.info(f"Purged  {count} entries from {table_name}, {server_id_val}.")
                for tab in matching_tables_2:
                    table_name,table_obj=tab
                    # loop over the table names and count the number of entries to be deleted.
                    count=session.query(table_obj).filter_by(server_profile_id=server_id_val).count()
                    self.logs.info(f"Purging in {table_name}, {server_id_val}.  {count} entries will be removed.")
                    
                    # Delete the records from the table where server_id equals X
                    session.query(table_obj).filter_by(server_profile_id=server_id_val).delete()
                    session.commit()
                    self.logs.info(f"Purged  {count} entries from {table_name}, {server_id_val}.")

            except IntegrityError as e:
                session.rollback()
                raise e
        



    async def reload_needed(self,changed_files):
        '''idea is to only load/unload changed files.'''
        for i, e in self.loaded_extensions.items():
            if not i in self.extension_list:
                await self.unload_extension(i)
                self.loaded_extensions[i]=None

        for ext in self.extension_list:
            if not ext in self.loaded_extensions: 
                await self.extension_loader(ext)
            else:
                val=await self.extension_reload(ext)
        gui.gprint(self.extension_list)


    async def reload_all(self,resync=False):
        for i, e in self.loaded_extensions.items():
            await self.unload_extension(i)
            self.loaded_extensions[i]=None

        for ext in self.extension_list:
            if not ext in self.loaded_extensions: 
                await self.extension_loader(ext)
            else: 
                val=await self.extension_reload(ext)
        gui.gprint(self.extension_list)
        if resync:
            await self.all_guild_startup()

    def pswitchload(self,pmode=False):
        #Once could load in a list of 'plugins' seperately, decided against.
        #since it just caused problems.
        return self.loaded_extensions

    async def extension_loader(self,extname,plugin=False):
        """Load an extension and add it to the internal loaded extension dictionary."""
        gui.gprint("STARTING LOAD FOR:", extname)
        self.pswitchload(plugin)[extname]=("settingup",None)
        try:
            gui.gprint("LOADING", extname)
            await self.load_extension(extname)
            self.pswitchload(plugin)[extname]=("running",None)
            return "LOADOK"
        except Exception as ex:
            en=str(ex)
            back=traceback.format_exception(None, ex, ex.__traceback__)
            gui.gprint("ENOK",back)
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
            
    def genid(self):
        return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=9))

    async def send_error_embed(self,emb=None,content=None):
        '''send error embed to debug channel.'''
        if self.error_channel:
            chan=self.get_channel(self.error_channel)
            await chan.send(content=content,embed=emb)
        
    async def send_error(self,error,title="ERROR"):
        '''Add an error to the internal log and the log channel.'''
        stack=traceback.format_exception(None, error, error.__traceback__)
        just_the_string=("".join([f"{replace_working_directory(s)}" for e, s in enumerate(stack)]))
        #just_the_string=''.join(stack)
        er=MessageTemplates.get_paged_error_embed(title=f"Error with {title}",description=f"{just_the_string},{str(error)}")
        er[-1].add_field(name="Details",value=f"{title},{error}")
        for e in er: await self.send_error_embed(e)



    @tasks.loop(seconds=10)
    async def status_ticker(self):
        await self.status_ticker_next()
            
        
        
    @tasks.loop(seconds=20.0)
    async def check_tc_tasks(self):
        '''run all TcTaskManager Tasks, fires every 20 seconds..'''
        await TCTaskManager.run_tasks()
        stat, panel=TCTaskManager.get_task_status()
        gui.DataStore.set('schedule',panel)
        self.add_act("taskstatus",stat)


    @tasks.loop(seconds=1.0)
    async def post_queue_message(self):
        #gui.gprint(self.latency)
        if self.guimode:
            gui.DataStore.add_value('latency',round(self.latency,7))
            #await self.gui.update_every_second()
            
            
        await self.post_queue_message_int()
        

    @tasks.loop(seconds=1.0)
    async def delete_queue_message(self):
        await self.delete_queue_message_int()
        

        
