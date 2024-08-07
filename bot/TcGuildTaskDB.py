from utility import urltomessage
from .Tasks.TCTasks import TCTask, TCTaskManager
from database import DatabaseSingleton
import sqlalchemy
import gui
from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    DateTime,
    delete,
    select,
)
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Tuple


import asyncio
import discord
from dateutil.rrule import rrule, rrulestr, WEEKLY, SU

Guild_Task_Base = declarative_base(name="Guild Scheduled Task Base")


class Guild_Task_Functions:
    """This class is a fancy dictionary that stores coroutines."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Guild_Task_Functions()
        return cls._instance

    def __init__(self):
        self.guildfunctions = {}

    @staticmethod
    def check_auto_channel(autochannel: discord.TextChannel) -> Tuple[bool, str]:
        """Check if the passed in autochannel has the needed permissions to become an auto_channel."""
        permissions = autochannel.permissions_for(autochannel.guild.me)
        permission_check_string = ""
        if not permissions.view_channel:
            permission_check_string = "I can't read view this channel.\n "
        if not permissions.read_messages:
            permission_check_string += "I can't read messages here.\n"
        if not permissions.read_message_history:
            permission_check_string += "I can't read message history here.\n"
        if not permissions.send_messages:
            permission_check_string += "I can't send messages.\n "
        if not permissions.manage_messages:
            permission_check_string += "I can't manage messages here.\n"
        if permission_check_string:
            result = f"I have one or more problems with the specified log channel {autochannel.mention}.  {permission_check_string}\n  Please update my permissions for this channel in particular."
            return False, result
        messagableperms = [
            "send_messages",
            "embed_links",
            "attach_files",
            "add_reactions",
            "use_external_emojis",
            "use_external_stickers",
            "read_message_history",
            "manage_webhooks",
        ]
        add = "."
        for p, v in permissions:
            if v:
                if p in messagableperms:
                    messagableperms.remove(p)
        if len(messagableperms) > 0:
            add = ", \n with the exception of: " + ",".join(messagableperms) + "."
        return True, "Needed permissions are set in this channel" + add

    @classmethod
    def add_task_function(cls, name, func):
        instance = cls.get_instance()
        if name in instance.guildfunctions:
            gui.gprint(f"Task function with name '{name}' already exists.")
        else:
            instance.guildfunctions[name] = func
            gui.gprint(f"Task function with name '{name}' added.")

    @classmethod
    def remove_task_function(cls, name):
        instance = cls.get_instance()
        if name in instance.guildfunctions:
            del instance.guildfunctions[name]
            gui.gprint(f"Task function with name '{name}' removed.")
        else:
            gui.gprint(f"Task function with name '{name}' does not exist.")

    @classmethod
    async def execute_task_function(cls, name, **kwargs):
        instance = cls.get_instance()
        gui.gprint(name)
        if name in instance.guildfunctions:
            gui.gprint(f"Executing task function with name '{name}', kwargs{kwargs}.")
            out = await instance.guildfunctions[name](**kwargs)
            gui.gprint(f"Successful execution task function with name '{name}'.")
            return out
        else:
            gui.gprint(f"Task function with name '{name}' does not exist.")
            return "DNE"


class TCGuildTask(Guild_Task_Base):
    """SQLAlchemy Table that stores data for Guild Tasks.
    Guild Tasks are tasks set up on a guild per guild basis, running after a fixed period
    of time."""

    __tablename__ = "tcguild_task"
    server_id = Column(Integer, nullable=False)
    task_name = Column(String, nullable=False)
    target_message_url = Column(String)
    target_channel_id = Column(Integer)
    task_id = Column(String)
    relativedelta_serialized = Column(String)
    use_target_url = Column(Boolean, default=False)
    next_run = Column(DateTime, default=datetime.now())
    remove_after = False

    __table_args__ = (PrimaryKeyConstraint("server_id", "task_name"),)

    def __init__(
        self,
        server_id: int,
        task_name: str,
        target_message: discord.Message,
        relativedelta_obj: rrule,
        use_target_url: bool = False,
    ):
        self.server_id = server_id
        self.task_name = task_name
        self.target_message_url = target_message.jump_url
        self.target_channel_id = target_message.channel.id
        self.task_id = f"{self.server_id}_{self.task_name}"
        self.use_target_url = use_target_url
        self.relativedelta_serialized = self.serialize_relativedelta(relativedelta_obj)

    @property
    def name(self):
        return f"{self.server_id}_{self.task_name}"

    def __repr__(self):
        return str(self)

    def __str__(self):
        stri = f"{self.name}, channel:{self.target_channel_id}\n{self.relativedelta_serialized}\n"
        return stri

    @staticmethod
    def add_guild_task(
        server_id: int,
        task_name: str,
        target_message: discord.Message,
        rdelta: rrule,
        use_message=False,
    ):
        """add a new TCGuildTask entry, using the server_id and task_name."""
        """server_id is the guild id, task_name is the name of the task."""

        new = TCGuildTask.get(server_id, task_name)
        if not new:
            session = DatabaseSingleton.get_session()
            new = TCGuildTask(
                server_id=server_id,
                task_name=task_name,
                target_message=target_message,
                relativedelta_obj=rdelta,
                use_target_url=use_message,
            )
            session.add(new)
            session.commit()
        gui.gprint(new)
        return new

    @classmethod
    def remove_guild_task(cls, server_id: int, task_name: Optional[str] = None):
        """
        Deletes TCGuildTask entries with the specified server_id and task_name,
        or all entries with the specified server_id if no task_name is specified.
        """
        session = DatabaseSingleton.get_session()
        if task_name:
            TCTaskManager.add_tombstone(f"{server_id}_{task_name}")
            session.execute(
                delete(TCGuildTask).where(
                    TCGuildTask.server_id == server_id,
                    TCGuildTask.task_name == task_name,
                )
            )
        else:
            tasks = (
                session.execute(
                    select(TCGuildTask.task_name).where(
                        TCGuildTask.server_id == server_id
                    )
                )
                .scalars()
                .all()
            )
            for task in tasks:
                TCTaskManager.add_tombstone(f"{server_id}_{task}")
            session.execute(
                delete(TCGuildTask).where(TCGuildTask.server_id == server_id)
            )
        session.commit()

    @classmethod
    def get_tasks_by_server_id(cls, server_id):
        """
        Returns a list of TCGuildTask objects for the specified server_id.
        """
        session = DatabaseSingleton.get_session()
        results = (
            session.execute(
                select(TCGuildTask).where(TCGuildTask.server_id == server_id)
            )
            .scalars()
            .all()
        )
        return results

    @classmethod
    def get(cls, server_id, task_name):
        """
        Returns the TCGuildTask entry for the specified server_id and task_name, or None if it doesn't exist.
        """
        session: Session = DatabaseSingleton.get_session()
        statement = select(TCGuildTask).where(
            TCGuildTask.server_id == server_id, TCGuildTask.task_name == task_name
        )
        result = session.execute(statement).scalar()
        if result:
            return result
        else:
            return None

    @classmethod
    def parent_callback(cls, guildtaskname: str, next_run: datetime):
        """
        Callback for whenever a task is done.
        """
        s, t = guildtaskname.split("_")
        cls.update(int(s), t, next_run)

    @classmethod
    def update(cls, server_id: int, task_name: str, next_run: datetime) -> None:
        """
        Updates the next_run attribute of the TCGuildTask entry with the
        specified server_id and task_name to the passed in datetime object.
        """
        session: Session = DatabaseSingleton.get_session()
        statement = select(TCGuildTask).where(
            TCGuildTask.server_id == server_id, TCGuildTask.task_name == task_name
        )
        task = session.execute(statement).scalar_one_or_none()
        if task:
            task.next_run = next_run
            gui.gprint(f"{task},UPDATED {task.next_run}")
            session.commit()
        else:
            raise Exception(
                f"No TCGuildTask entry found for server_id={server_id} and task_name={task_name}"
            )

    async def guild_task(self, bot, server_id, task_name):
        """This function is passed into TCTask as the wrapped function."""
        this_out = "NA"
        try:
            gui.dprint(server_id, task_name)
            channel = bot.get_channel(self.target_channel_id)
            source_message = None
            if self.use_target_url:
                try:
                    source_message = await urltomessage(self.target_message_url, bot)
                except Exception as e:
                    await bot.send_error(e, "ERROR GETTING MESSAGE")
                    this_out = "REMOVE"
            else:
                source_message = await channel.send(
                    f"Auto Guild Task {self.task_name} launching."
                )
            if source_message:
                this_out = await Guild_Task_Functions.execute_task_function(
                    self.task_name, source_message=source_message
                )
        except Exception as e:
            if isinstance(e, sqlalchemy.orm.exc.DetachedInstanceError):
                gui.dprint("DetachedInstanceError occurred.")
                TCGuildTask.remove_guild_task(server_id, task_name)
            else:
                await bot.send_error(e, "AUTO COMMAND ERROR.")
                gui.dprint("Another error occurred.")
        await asyncio.sleep(2)
        gui.gprint(f"{self.name} Task done at", datetime.now(), "excution ok.")
        if self.remove_after or this_out == "REMOVE":
            print("removing task.")
            TCGuildTask.remove_guild_task(self.server_id, self.task_name)

    def to_task(self, bot):
        """Initalize a TCTask object with name {self.server_id}_{self.task_name}"""
        rd = self.deserialize_relativedelta(self.relativedelta_serialized)
        # thename=f"{self.server_id}_{self.task_name}"
        gui.gprint("adding task for ", str(self))
        if not TCTaskManager.does_task_exist(self.name):
            tc = TCTask(
                name=self.name,
                time_interval=rd,
                next_run=self.next_run,
                parent_db=TCGuildTask,
            )
            tc.assign_wrapper(
                lambda: self.guild_task(bot, self.server_id, self.task_name)
            )
        else:
            raise Exception("Task is already in the manager.")

    def change_next_run(self, bot, next_datetime):
        """change the next time the task is going to run"""
        rd = self.deserialize_relativedelta(self.relativedelta_serialized)
        thename = f"{self.server_id}_{self.task_name}"
        gui.gprint("changing next run for ", str(self))
        if TCTaskManager.does_task_exist(thename):
            TCTaskManager.change_task_time(thename, next_datetime)
        else:
            raise Exception("Task is not in the manager.")

    def change_rrule(self, bot, new_rrule):
        """change the rrule for this task."""
        rd = self.serialize_relativedelta(new_rrule)
        thename = f"{self.server_id}_{self.task_name}"
        gui.gprint("changing rrule for ", str(self))
        if TCTaskManager.does_task_exist(thename):
            res = TCTaskManager.change_task_interval(thename, new_rrule)
            if res:
                self.relativedelta_serialized = rd
                self.next_run = res
            DatabaseSingleton.get_session().commit()
        else:
            raise Exception("Task is not in the manager.")

    def deserialize_relativedelta(self, rd_json):
        try:
            to_return = rrulestr(rd_json)
            return to_return
        except Exception as e:
            start_date = datetime(2023, 1, 1, 16, 0)

            # Create a rule for weekly recurrence on Sundays
            rule = rrule(freq=WEEKLY, byweekday=SU, dtstart=start_date)

            self.relativedelta_serialized = str(rule)
            DatabaseSingleton("sa").commit()
            return rule

    def serialize_relativedelta(self, rd):
        return str(rd)

    def get_status_desc(self):
        next_date = f"<t:{int(self.next_run.timestamp())}:f>"
        auto_log_chan = f"<#{self.target_channel_id}>"
        output = f"Auto Log Channel:{auto_log_chan}\nNext Run Time:{next_date}"
        return output
