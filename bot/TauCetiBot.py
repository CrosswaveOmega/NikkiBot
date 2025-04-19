from __future__ import annotations

import asyncio
import configparser
import datetime
import logging
import os
import random
import string
import traceback
from typing import Dict, Optional, Tuple

import discord
from discord import Interaction
from discord.app_commands import CommandTree
from discord.ext import commands, tasks
from javascriptasync import JSContext
from javascriptasync.logging import get_filehandler, setup_logging
from sqlalchemy.exc import IntegrityError

import gptmod
import gui
from utility import Chelp, MessageTemplates, replace_working_directory
import database
from .PlaywrightAPI import PlaywrightMixin
from .StatusMessages import StatusMessage, StatusMessageManager, StatusMessageMixin
from .Tasks.TCTasks import TCTaskManager
from .TCAppCommandAutoSync import Guild_Sync_Base, SpecialAppSync
from .TcGuildTaskDB import Guild_Task_Base, TCGuildTask
from .TCMixins import CogFieldList, StatusTicker

""" Primary Class

This file is for an extended Bot Class for this Discord Bot.


"""


class IntegrationCreateFilter(logging.Filter):
    def filter(self, record):
        # Check if the log record's level is DEBUG and message contains "INTERACTION_CREATE"
        if record.levelno == logging.DEBUG:
            if "INTERACTION_CREATE" in record.getMessage():
                return True
            return False
        return True


intent = discord.Intents.default()
intent.presences = True
intent.message_content = True
intent.guilds = True
intent.members = True


class ConfigParserSub(configparser.ConfigParser):
    def get(self, section, option, fallback=None, **kwargs):
        return super().get(section, option, fallback=fallback, **kwargs)

    def getbool(self, option, fallback=None, **kwargs):
        return super().getboolean("feature", option, fallback=False, **kwargs)


class TreeOverride(CommandTree):
    # I need to do this just to get a global check on app_commands...
    async def interaction_check(self, interaction: Interaction) -> bool:
        """Don't fire if the user wants to be ignored, but ensure that the
        user can unignore themselves later."""
        if interaction.command:
            if interaction.command.extras:
                if "nocheck" in interaction.command.extras:
                    return True
        uid = interaction.user.id
        if database.Users_DoNotTrack.check_entry(uid):
            return False
        return True

    async def _call(self, interaction: Interaction):
        # because there's no global before invoke for app commands.
        if not await self.interaction_check(interaction):
            interaction.command_failed = True
            return
        if interaction.command:
            gui.gprint("app command call: ", interaction.command.name)
        await super()._call(interaction)


class TCBot(
    commands.Bot,
    CogFieldList,
    StatusTicker,
    StatusMessageMixin,
    SpecialAppSync,
    PlaywrightMixin,
):
    """A new central bot class.
    An extension of discord.py's Bot class with additional functionality."""

    def __init__(self, guimode=False):
        super().__init__(
            command_prefix=["tc>", ">"],
            tree_cls=TreeOverride,
            help_command=Chelp(),
            intents=intent,
        )
        # The Database Singleton is initalized in here.
        print("Starting up bot.")
        self.database: database.database_singleton.DatabaseSingleton = (
            database.database_singleton.DatabaseSingleton("sd")
        )

        self.keys = {}
        self.gptapi: gptmod.GptmodAPI = None
        self.error_channel: int = None
        print("JS CONTEXT setup")
        self.jsenv: JSContext = JSContext()
        print("done")
        self.config: ConfigParserSub = ConfigParserSub()
        self.exit_status: str = "none"
        self.statmess: StatusMessageManager = StatusMessageManager(self)

        self.logs = logging.getLogger("TCLogger")
        self.loggersetup()
        self.embedding = gptmod.GenericThread(gptmod.warmup)
        # self.embedding.run()

        self.extensiondir, self.extension_list = "", []
        self.plugindir, self.plugin_list = "", []
        self.guimode = False
        self.gui = None

        self.loaded_extensions: Dict[str, Tuple[str, Optional[str]]] = {}
        self.loaded_plugins: Dict[str, Tuple[str, Optional[str]]] = {}
        self.default_error = self.on_command_error
        self.bot_ready = False

    async def database_on(self):
        """turn the database on."""
        self.database = database.DatabaseSingleton("Startup")
        self.database.load_base(Base=Guild_Task_Base)
        self.database.load_base(Base=Guild_Sync_Base)
        await self.database.startup_all()

    def set_error_channel(self, newid: int):
        """set the error channel id."""
        if str(newid).isdigit():
            self.error_channel = int(newid)
            return True
        return False

    async def after_startup(self):
        """This function is called in on_ready, but only once."""
        if not self.bot_ready:
            # Start up the GuiPanel
            await self.jsenv.init_js_a()
            setup_logging(
                logging.DEBUG, handler=get_filehandler(log_level=logging.DEBUG)
            )
            guimode = self.config.getbool("gui")
            debugmode = self.config.getbool("debug")
            if debugmode:
                gui.toggle_debug_mode(debugmode)
            if guimode:
                self.guimode = True
                self.gui = gui.Gui()
            if self.guimode:
                self.gui.run(self.loop)
                pass
                # self.gthread=gui.Gui.run(self.gui)
            self.gptapi = gptmod.GptmodAPI()
            print("Turning on db")
            await self.database_on()

            # Update extensions.
            self.update_ext_list()
            await self.reload_all()
            await self.database.get_instance().sync_all()
            dbcheck = await self.database.database_check()
            gui.gprint(dbcheck)
            # audit old guild data.
            await self.audit_guilds()

            # Sync to all needed servers.
            await self.all_guild_startup()
            gui.gprint("BOT SYNC complete!")
            self.delete_queue_message.start()  # pylint:ignore
            self.post_queue_message.start()  # pylint:ignore
            self.status_ticker.start()  # pylint:ignore
            for g in self.guilds:
                mytasks = TCGuildTask.get_tasks_by_server_id(g.id)
                for t in mytasks:
                    t.to_task(self)

            self.bot_ready = True

            # start playwright
            pmode = self.config.getboolean("feature", "playwright")
            print("playwrighter", pmode)
            # if pmode == True:
            #    await self.start_player()
            now = datetime.datetime.now()
            seconds_until_next_minute = (60 - now.second) % 20
            gui.gprint("sleeping for ", seconds_until_next_minute)

            await asyncio.sleep(seconds_until_next_minute)
            self.check_tc_tasks.start()

            # Start the coroutine

    async def close(self):
        print("Signing off.")
        # Close the SQLAlchemy engine

        await self.database.close_out()
        # Logout the bot from Discord
        self.post_queue_message.cancel()
        self.delete_queue_message.cancel()
        self.check_tc_tasks.cancel()
        self.status_ticker.cancel()
        del self.jsenv
        # close the gui
        if self.gui:
            await self.gui.kill()
        if self.playapi:
            try:
                try:
                    await asyncio.wait_for(self.close_browser(), timeout=8)
                except Exception as ex:
                    print("rt", ex)
                print("done closing.")
                await self.playapi.stop()
                print()
            except Exception as e:
                # l=logging.getLogger("TCLogger")
                self.logs.error(str(e), exc_info=e)
        print("close done?")

        await super().close()

    def loggersetup(self):
        """Setup the loggers for the bot."""
        if not os.path.exists("./logs/"):
            os.makedirs("./logs/")
        handler2 = logging.handlers.RotatingFileHandler(
            filename="./logs/discord.log",
            encoding="utf-8",
            maxBytes=7 * 1024 * 1024,  # 32 MiB
            backupCount=5,  # Rotate through 5 files
        )
        dt_fmt = "%Y-%m-%d %H:%M:%S"
        formatter2 = logging.Formatter(
            "[LINE] [{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
        )
        handler2.setFormatter(formatter2)
        # handler2.addFilter(IntegrationCreateFilter("logfilter"))
        discord.utils.setup_logging(level=logging.INFO, handler=handler2, root=False)
        
        jslogs = logging.getLogger("asyncjs").setLevel(logging.INFO)
        self.logs = logging.getLogger("TCLogger")
        self.logs.setLevel(logging.INFO)
        handlerTC = logging.handlers.RotatingFileHandler(
            filename="./logs/tauceti__log.log",
            encoding="utf-8",
            maxBytes=32 * 1024 * 1024,  # 32 MiB
            backupCount=5,  # Rotate through 5 files
        )
        dt_fmt = "%Y-%m-%d %H:%M:%S"
        formatter4 = logging.Formatter(
            "[LINE] [{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
        )
        handlerTC.setFormatter(formatter4)
        self.logs.addHandler(handlerTC)
        zehttp = logging.getLogger("discord.http")
        zehttp.setLevel(logging.WARNING)
        handler = logging.handlers.RotatingFileHandler(
            filename="./logs/discord_http.log",
            encoding="utf-8",
            maxBytes=32 * 1024 * 1024,  # 32 MiB
            backupCount=5,  # Rotate through 5 files
        )
        dt_fmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter(
            "[LINE] [{asctime}] [{levelname:<8}] {name}: {message}", dt_fmt, style="{"
        )
        handler.setFormatter(formatter)
        zehttp.addHandler(handler)

    def set_ext_directory(self, dir: str):
        """Set the directory with extensions."""
        self.extensiondir = dir

    def update_ext_list(self):
        """Update the internal exension list."""
        self.extension_list = []
        for filename in os.listdir(self.extensiondir):
            gui.gprint(filename)
            if filename.endswith(".py"):
                extensionname = f"cogs.{filename[:-3]}"
                gui.gprint(extensionname)
                self.extension_list.append(extensionname)

    def add_status_message(self, ctx) -> StatusMessage:
        """return a status message object"""
        cid = self.statmess.add_status_message(ctx)
        return self.statmess.get_message_obj(cid)

    async def audit_guilds(self, override_for: int = None):
        """audit guilds."""
        metadata = self.database.get_metadata()
        matching_tables = []
        matching_tables_2 = []
        for table_name in metadata.tables.keys():
            table = metadata.tables[table_name]
            if "server_id" in table.columns.keys():
                matching_tables.append((table_name, table))
            if "server_profile_id" in table.columns.keys():
                matching_tables_2.append((table_name, table))

        # gui.gprint the tables found with matching column name
        gui.gprint(", ".join(f[0] for f in matching_tables))

        guilds_im_in = []
        for guild in self.guilds:
            gui.gprint(guild.id, override_for)
            if guild.id != override_for:
                guilds_im_in.append(guild.id)
        audit_results = database.ServerData.Audit(guilds_im_in)
        to_purge = [auditme.server_id for auditme in audit_results]
        self.logs.info(audit_results)
        session = self.database.get_session()
        for server_id_val in to_purge:
            try:
                for tab in matching_tables:
                    table_name, table_obj = tab
                    # loop over the table names and delete the entries
                    count = (
                        session.query(table_obj)
                        .filter_by(server_id=server_id_val)
                        .count()
                    )
                    self.logs.info(
                        f"Purging in {table_name}, {server_id_val}.  {count} entries will be removed."
                    )

                    # Delete the records from the table where server_id equals X
                    session.query(table_obj).filter_by(server_id=server_id_val).delete()
                    session.commit()
                    self.logs.info(
                        f"Purged  {count} entries from {table_name}, {server_id_val}."
                    )
                for tab in matching_tables_2:
                    table_name, table_obj = tab
                    # loop over the table names and count the number of entries to be deleted.
                    count = (
                        session.query(table_obj)
                        .filter_by(server_profile_id=server_id_val)
                        .count()
                    )
                    self.logs.info(
                        f"Purging in {table_name}, {server_id_val}.  {count} entries will be removed."
                    )

                    # Delete the records from the table where server_id equals X
                    session.query(table_obj).filter_by(
                        server_profile_id=server_id_val
                    ).delete()
                    session.commit()
                    self.logs.info(
                        f"Purged  {count} entries from {table_name}, {server_id_val}."
                    )

            except IntegrityError as e:
                session.rollback()
                raise e

    async def reload_needed(self, changed_files):
        """idea is to only load/unload changed files."""
        for i, e in self.loaded_extensions.items():
            if i not in self.extension_list:
                await self.unload_extension(i)
                self.loaded_extensions[i] = None

        for ext in self.extension_list:
            if ext not in self.loaded_extensions:
                await self.extension_loader(ext)
            else:
                val = await self.extension_reload(ext)
        gui.gprint(self.extension_list)

    async def reload_all(self, resync=False):
        for i, e in self.loaded_extensions.items():
            try:
                await self.unload_extension(i)
            except commands.errors.ExtensionNotFound as e:
                await self.send_error(e, "Could not find extension!", True)
            except commands.errors.ExtensionNotLoaded as e:
                await self.send_error(e, "ERROR", True)

            self.loaded_extensions[i] = None

        for ext in self.extension_list:
            if ext not in self.loaded_extensions:
                await self.extension_loader(ext)
            else:
                val = await self.extension_reload(ext)
        gui.gprint(self.extension_list)
        if resync:
            await self.all_guild_startup()

    async def reload_one(self, ext, resync=False):
        reload_this = []
        for i, e in self.loaded_extensions.items():
            if i != ext:
                continue
            try:
                await self.unload_extension(i)
                reload_this.append(i)
            except commands.errors.ExtensionNotFound as e:
                await self.send_error(e, "Could not find extension!", True)
            except commands.errors.ExtensionNotLoaded as e:
                await self.send_error(e, "ERROR", True)

            self.loaded_extensions[i] = None

        for ext in reload_this:
            if ext not in self.loaded_extensions:
                await self.extension_loader(ext)
            else:
                val = await self.extension_reload(ext)

    def pswitchload(self, pmode=False):
        # Once could load in a list of 'plugins' seperately, decided against.
        # since it just caused problems.
        return self.loaded_extensions

    async def extension_loader(self, extname, plugin=False):
        """Load an extension and add it to the internal loaded extension dictionary."""
        gui.gprint("STARTING LOAD FOR:", extname)
        self.pswitchload(plugin)[extname] = ("settingup", None)
        try:
            gui.gprint("LOADING", extname)
            await self.load_extension(extname)
            self.pswitchload(plugin)[extname] = ("running", None)
            return "LOADOK"
        except Exception as ex:
            en = str(ex)
            await self.send_error(ex, "ERROR", True)
            back = traceback.format_exception(None, ex, ex.__traceback__)
            gui.gprint("ENOK", back)
            tracebackstr = "".join(
                traceback.format_exception(None, ex, ex.__traceback__)
            )
            self.pswitchload(plugin)[extname] = (en, tracebackstr)
            return tracebackstr

    async def extension_reload(self, extname, plugin=False):
        """reload an extension by EXTNAME."""
        if extname not in self.pswitchload(plugin):
            return "NOTFOUND"
        if extname in self.pswitchload(plugin):
            self.pswitchload(plugin)[extname] = ("settingup", None)
            try:
                await self.reload_extension(extname)
                self.pswitchload(plugin)[extname] = ("running", None)
                return "RELOADOK"
            except commands.ExtensionNotLoaded:
                return await self.extension_loader(extname)
            except Exception as ex:
                await self.send_error(ex, "ERROR", True)
                en = str(ex)
                tracebackstr = "".join(
                    traceback.format_exception(None, ex, ex.__traceback__)
                )
                self.pswitchload(plugin)[extname] = (en, tracebackstr)
                return tracebackstr

    def genid(self):
        return "".join(
            random.choices(string.ascii_uppercase + string.ascii_lowercase, k=9)
        )

    async def send_error_embed(self, emb=None, content=None):
        """send error embed to debug channel."""
        if self.error_channel:
            try:
                chan = self.get_channel(self.error_channel)
                await chan.send(content=content, embed=emb)
            except Exception as e:
                self.bot.logs.error("could not send %s", str(e))

    async def send_error(self, error, title="ERROR", uselog=False):
        if uselog:
            log = logging.getLogger("discord")
            log.error("An error has been raised: %s", title, exc_info=error)
        stack = traceback.format_exception(None, error, error.__traceback__)

        just_the_string = "".join(
            [f"{replace_working_directory(s)}" for e, s in enumerate(stack)]
        )
        # just_the_string=''.join(stack)
        er = MessageTemplates.get_paged_error_embed(
            title=f"Error with {title}"[:200],
            description=f"{just_the_string},{str(error)}"[:4000],
        )
        er[-1].add_field(name="Details", value=f"{title},{error}"[:1020])
        for e in er:
            await self.send_error_embed(e)

    @tasks.loop(seconds=120)
    async def status_ticker(self):
        await self.status_ticker_next()

    @tasks.loop(seconds=20.0)
    async def check_tc_tasks(self):
        """run all TcTaskManager Tasks, fires every 20 seconds."""
        await TCTaskManager.run_tasks()
        stat, panel = TCTaskManager.get_task_status()
        gui.DataStore.set("schedule", panel)
        self.add_act("taskstatus", stat)

    @tasks.loop(seconds=1.0)
    async def post_queue_message(self):
        # gui.gprint(self.latency)
        if self.guimode:
            gui.DataStore.add_value("latency", round(self.latency, 7))
            # await self.gui.update_every_second()

        await self.post_queue_message_int()

    @tasks.loop(seconds=1.0)
    async def delete_queue_message(self):
        await self.delete_queue_message_int()
