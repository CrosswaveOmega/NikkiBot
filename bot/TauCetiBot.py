from typing import Any
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
from database import *
from .TCTasks import TCTaskManager
from sqlalchemy.exc import IntegrityError
from utility import Chelp, urltomessage, MessageTemplates
from .TcGuildTaskDB import Guild_Task_Base, Guild_Task_Functions, TCGuildTask
from .GuildSyncStatus import Guild_Sync_Base, AppGuildTreeSync, format_application_commands
from .TCMixins import CogFieldList, StatusTicker
""" Primary Class

This file is for an extended Bot Class for this Discord Bot.


"""

intent=discord.Intents.default();
intent.presences=True
intent.message_content=True
intent.guilds=True
intent.members=True
from database import DatabaseSingleton
from .StatusMessages import StatusMessageManager, StatusMessage, StatusMessageMixin

class TCBot(commands.Bot, CogFieldList,StatusTicker,StatusMessageMixin):
    
    """TC's central bot class.  An extension of discord.py Bot class with additional functionality."""
    def __init__(self):
        super().__init__(command_prefix=['tc>',">"], help_command=Chelp(), intents=intent)
        #The Database Singleton is initalized in here.
        self.database=None

        self.error_channel=None

        self.statmess:StatusMessageManager=StatusMessageManager(self)

        self.logs=logging.getLogger("TCLogger")
        self.loggersetup()

        self.extensiondir,self.extension_list="",[]
        self.plugindir,self.plugin_list="",[]

        self.loaded_extensions={}
        self.loaded_plugins={}


        
        
        self.default_error=self.on_command_error
        self.bot_ready=False

    def database_on(self):
        '''turn the database on.'''
        self.database= DatabaseSingleton("Startup")
        self.database.startup()
        self.database.load_base(Base=Guild_Task_Base)
        self.database.load_base(Base=Guild_Sync_Base)

    def set_error_channel(self,newid):
        if str(newid).isdigit():
            self.error_channel=int(newid)
            print("PASS")
            return True
        return False

    async def after_startup(self):
        '''This function is called in on_ready, but only once.'''
        if not self.bot_ready:
            await self.all_guild_startup()
            print("BOT SYNCED!")
            self.delete_queue_message.start()
            self.post_queue_message.start()
            self.status_ticker.start()
            for g in self.guilds:
                mytasks=TCGuildTask.get_tasks_by_server_id(g.id)
                for t in mytasks:
                    t.to_task(self)
            self.bot_ready=True
            now = datetime.datetime.now()
            seconds_until_next_minute = (60 - now.second)%20
            print('sleeping for ',seconds_until_next_minute)
            await asyncio.sleep(seconds_until_next_minute)
            self.check_tc_tasks.start()
            # Start the coroutine

    async def on_close(self):
        # Close the SQLAlchemy engine
        self.database.close_out()
        # Logout the bot from Discord
        self.post_queue_message.cancel()
        self.delete_queue_message.cancel()
        self.check_tc_tasks.cancel()
        self.status_ticker.cancel()
        await self.logout()

    def loggersetup(self):
        if not os.path.exists('./logs/'):
            os.makedirs('./logs/')

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
        file_handler = logging.FileHandler("./logs/sqlalchemy.log")
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
    
    async def sync_enabled_cogs_for_guild(self,guild, force=False):
        '''With a passed in guild, sync all activated cogs for that guild.'''        
        def syncprint(lis):
            pass
            #print(f"Sync for {guild.name} (ID {guild.id})",lis)
        def should_skip_cog(cogname: str) -> bool:
            """Determine whether a cog should be skipped during synchronization."""
            '''Not currently needed.'''
            return False

        def add_command_to_tree(command, guild):
            """Add a command to the commands tree for the given guild."""
            current_command_list=[]
            if isinstance(command, (commands.HybridCommand, commands.HybridGroup)):
                try:
                    self.tree.add_command(command.app_command, guild=guild, override=True)
                    
                    if isinstance(command,commands.HybridGroup):
                        for i in command.walk_commands():
                            if isinstance(i.app_command,discord.app_commands.Command):
                                current_command_list.append(i.app_command)
                    else:
                        current_command_list.append(command.app_command)
                    syncprint(f"Added hybrid {command.name}")
                except:
                    syncprint(f"Cannot add {command.name}, case error.")
            else:
                try:
                    self.tree.add_command(command, guild=guild, override=True)
                    if isinstance(command,discord.app_commands.Group):
                        for i in command.walk_commands():
                            if isinstance(i,discord.app_commands.Command):
                                current_command_list.append(i)
                    else:
                        current_command_list.append(command)
                    syncprint(f"Added {command.name}")
                except:
                    syncprint(f"Cannot add {command.name}, this is not a app command")
            return current_command_list

        async def sync_commands_tree(guild,synced, forced=False):
            """Sync the commands tree for the given guild."""
            print(f"Checking if it's time to sync commands syncing for {guild.name} (ID {guild.id})...")
            try:
                app_tree=format_application_commands(synced)
                dbentry=AppGuildTreeSync.get(guild.id)
                if not dbentry:
                    dbentry=AppGuildTreeSync.add(guild.id)
                if (dbentry.compare_with_command_tree(app_tree)!=None) or forced==True:
                    print(f"Beginning command syncing for {guild.name} (ID {guild.id})...")
                    dbentry.update(app_tree)
                    print(dbentry.compare_with_command_tree(app_tree))
                    await self.tree.sync(guild=guild)
                    print(f"Sync complete for {guild.name} (ID {guild.id})...")
            except Exception as e:
                print(str(e))

        """Gather all activated cogs for a given guild."""
        """Note, the reason it goes one by one is because it was originally intended to activate/deactivate cogs"""
        """On a server per server basis."""
        synced=[]
        for cogname, cog in self.cogs.items():
            if should_skip_cog(cogname):
                print("skipping cog ",cogname)
                continue
            for command in cog.walk_commands():
                synced+=add_command_to_tree(command, guild)
            for command in cog.walk_app_commands():
                synced+=add_command_to_tree(command, guild)

        await sync_commands_tree(guild,synced, forced=force)
        


    async def all_guild_startup(self, force=False):
        async for guild in self.fetch_guilds(limit=10000):
            print(f"syncing for {guild.name}")
            await self.sync_enabled_cogs_for_guild(guild,force=force)

    async def audit_guilds(self):
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

        # print the tables found with matching column name
        print(matching_tables)
        
        guilds_im_in=[]
        for guild in self.guilds:
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
                    # loop over the table names and delete the entries
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
            #else:                 val=await self.extension_reload(ext)
        print(self.extension_list)


    async def reload_all(self):
        for i, e in self.loaded_extensions.items():
            if not i in self.extension_list:
                await self.unload_extension(i)
                self.loaded_extensions[i]=None

        for ext in self.extension_list:
            if not ext in self.loaded_extensions: 
                await self.extension_loader(ext)
            else: 
                val=await self.extension_reload(ext)
        print(self.extension_list)

    def pswitchload(self,pmode=False):
        #Once could load in a list of 'plugins' seperately, decided against.
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
            
    def genid(self):
        return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase, k=9))

    async def send_error_embed(self,emb=None,content=None):
        '''send error embed to debug channel.'''
        if self.error_channel:
            chan=self.get_channel(self.error_channel)
            await chan.send(content=content,embed=emb)
        
    async def send_error(self,error,title="ERROR"):
        '''Add an error to the log'''
        just_the_string=''.join(traceback.format_exception(None, error, error.__traceback__))
        er=MessageTemplates.get_error_embed(title=f"Error with {title}",description=f"{just_the_string},{str(error)}")
        er.add_field(name="Details",value=f"{title},{error}")
        await self.send_error_embed(er)




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
        try:
            await ctx.send(embed=emb)
        except Exception as e:
            self.logs.error(str(e))
        await self.send_error_embed(er)



    @tasks.loop(seconds=10)
    async def status_ticker(self):
        await self.status_ticker_next()
            
        
        
    @tasks.loop(seconds=20.0)
    async def check_tc_tasks(self):
        '''run all TcTaskManager Tasks, fires every minute.'''
        await TCTaskManager.run_tasks()
        stat=TCTaskManager.get_task_status()
        self.add_act("taskstatus",stat)


    @tasks.loop(seconds=1.0)
    async def post_queue_message(self):
        await self.post_queue_message_int(self)
        

    @tasks.loop(seconds=1.0)
    async def delete_queue_message(self):
        await self.delete_queue_message_int()
        

        
