from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from dateutil.relativedelta import relativedelta
from utility import urltomessage, relativedelta_sp
from typing import Tuple
import json
import asyncio
import discord

Guild_Task_Base = declarative_base()
from database import DatabaseSingleton
from .TCTasks import TCTask, TCTaskManager

class Guild_Task_Functions:
    '''This class is a fancy dictionary that stores coroutines.'''
    _instance = None
    

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Guild_Task_Functions()
        return cls._instance

    def __init__(self):
        self.guildfunctions={}
        
    @staticmethod
    def check_auto_channel(autochannel:discord.TextChannel) -> Tuple[bool, str]:
        '''Check if the passed in autochannel has the needed permissions to become an auto_channel.'''
        permissions = autochannel.permissions_for(autochannel.guild.me)
        permission_check_string=""
        if not permissions.view_channel:
            permission_check_string="I can't read view this channel.\n "
        if not permissions.read_messages:
            permission_check_string+="I can't read messages here.\n"
        if not permissions.read_message_history:
            permission_check_string+="I can't read message history here.\n"
        if not permissions.send_messages:
            permission_check_string+="I can't send messages.\n "
        if not permissions.manage_messages:
            permission_check_string+="I can't manage messages here.\n"
        if permission_check_string:
            result=f"I have one or more problems with the specified log channel {autochannel.mention}.  {permission_check_string}\n  Please update my permissions for this channel in particular."
            return False, result
        messagableperms=['send_messages','embed_links','attach_files','add_reactions','use_external_emojis','use_external_stickers','read_message_history','manage_webhooks' ]
        add="."
        for p, v in permissions:
            if v:
                if p in messagableperms:
                    messagableperms.remove(p)
        if len(messagableperms)>0:
            add=", \n with the exception of: "+",".join(messagableperms)+"."
        return True, "Needed permissions are set in this channel"+add
    
    @classmethod
    def add_task_function(cls, name, func):
        instance = cls.get_instance()
        if name in instance.guildfunctions:
            print(f"Task function with name '{name}' already exists.")
        else:
            instance.guildfunctions[name] = func
            print(f"Task function with name '{name}' added.")

    @classmethod
    def remove_task_function(cls, name):
        instance = cls.get_instance()
        if name in instance.guildfunctions:
            del instance.guildfunctions[name]
            print(f"Task function with name '{name}' removed.")
        else:
            print(f"Task function with name '{name}' does not exist.")

    @classmethod
    async def execute_task_function(cls, name, **kwargs):
        instance = cls.get_instance()
        print(name)
        if name in instance.guildfunctions:
            print(f"Executing task function with name '{name}', kwargs{kwargs}.")
            await instance.guildfunctions[name](**kwargs)
            print(f"Successful execution task function with name '{name}'.")
        else:
            print(f"Task function with name '{name}' does not exist.")


class TCGuildTask(Guild_Task_Base):
    '''table to store data for Automatic guild tasks.'''
    __tablename__ = 'tcguild_task'
    server_id = Column(Integer, nullable=False)
    task_name = Column(String, nullable=False)
    target_message_url = Column(String)
    target_channel_id = Column(Integer)
    task_id = Column(String)
    relativedelta_serialized = Column(String)
    next_run = Column(DateTime, default=datetime.now())

    __table_args__ = (
        PrimaryKeyConstraint('server_id', 'task_name'),
    )

    def __init__(self, server_id, task_name, target_message, relativedelta_obj):
        self.server_id = server_id
        self.task_name = task_name
        self.target_message_url=target_message.jump_url
        self.target_channel_id=target_message.channel.id
        self.task_id=f"{self.server_id}_{self.task_name}"
        self.relativedelta_serialized = self.serialize_relativedelta(relativedelta_obj)
        
    @staticmethod
    def add_guild_task(server_id,task_name,target_message,rdelta):
        '''add a new TCGuildTask entry, using the server_id and task_name.'''
        '''server_id is the guild id, task_name is the name of the task.'''
        print(server_id,task_name,target_message.jump_url,rdelta)
        new=TCGuildTask.get(server_id,task_name)
        if not new:
            session=DatabaseSingleton.get_session()
            new = TCGuildTask(server_id=server_id,task_name=task_name,
                target_message=target_message,relativedelta_obj=rdelta)
            session.add(new)
            session.commit()
        return new
    
    @classmethod
    def remove_guild_task(cls, server_id, task_name=None):
        """
        Deletes TCGuildTask entries with the specified server_id and task_name,
        or all entries with the specified server_id if no task_name is specified.
        """
        session = DatabaseSingleton.get_session()
        if task_name:
            TCTaskManager.remove_task(f"{server_id}_{task_name}")
            session.query(TCGuildTask).filter_by(server_id=server_id, task_name=task_name).delete()
        else:
            tasks = session.query(cls.task_name).filter_by(server_id=server_id).all()
            for task in tasks:
                TCTaskManager.remove_task(f"{server_id}_{task.task_name}")
            session.query(TCGuildTask).filter_by(server_id=server_id).delete()
        session.commit()
        
    @classmethod
    def get_tasks_by_server_id(cls, server_id):
        """
        Returns a list of TCGuildTask objects for the specified server_id.
        """
        session = DatabaseSingleton.get_session()
        results = session.query(TCGuildTask).filter_by(server_id=server_id).all()
        return results
    
    @classmethod
    def get(cls, server_id, task_name):
        """
        Returns the entire TCGuildTask entry for the specified server_id and task_name, or None if it doesn't exist.
        """
        session:Session = DatabaseSingleton.get_session()
        result = session.query(TCGuildTask).filter_by(server_id=server_id,task_name=task_name).first()
        if result:            return result
        else:            return None
    @classmethod
    def update(cls, server_id, task_name, next_run):
        """
        Updates the next_run attribute of the TCGuildTask entry with the specified server_id and task_name to the passed in datetime object.
        """
        session:Session = DatabaseSingleton.get_session()
        task = session.query(TCGuildTask).filter_by(server_id=server_id, task_name=task_name).first()
        if task:
            task.next_run = next_run
            print(f"UPDATED {task.next_run}")
            session.commit()
        else:
            raise Exception(f"No TCGuildTask entry found for server_id={server_id} and task_name={task_name}")

    async def guild_task(self, bot):
        '''This function is passed into TCTask as the wrapped function.  '''
        try:
            channel=bot.get_channel(self.target_channel_id)
            source_message=await channel.send(f"Auto Guild Task {self.task_name} launching.")
            await Guild_Task_Functions.execute_task_function(
                self.task_name, source_message=source_message)
        except Exception as e:
            await bot.send_error(e,"AUTO COMMAND ERROR.")
        await asyncio.sleep(4)
        print("Task done at", datetime.now(),"excution ok.")

    def to_task(self,bot):
        '''Initalize a TCTask object with name {self.server_id}_{self.task_name}'''
        rd = self.deserialize_relativedelta(self.relativedelta_serialized)
        thename=f"{self.server_id}_{self.task_name}"
        print(thename,rd,self.target_message_url)
        if not TCTaskManager.does_task_exist(thename):
            tc=TCTask(name=thename, time_interval=rd, next_run=self.next_run,parent_db=TCGuildTask)
            print(self.next_run)
            tc.assign_wrapper(lambda: self.guild_task(bot))
        else:
            raise Exception("Task is already in the manager.")
    def change_next_run(self,bot, next_datetime):
        '''Initalize a TCTask object with name {self.server_id}_{self.task_name}'''
        rd = self.deserialize_relativedelta(self.relativedelta_serialized)
        thename=f"{self.server_id}_{self.task_name}"
        print(thename,rd,self.target_message_url)
        if  TCTaskManager.does_task_exist(thename):
            TCTaskManager.change_task_time(thename,next_datetime)
        else:
            raise Exception("Task is not in the manager.")  
    def deserialize_relativedelta(self, rd_json):
        rd_kwargs = json.loads(rd_json)
        return relativedelta_sp(**rd_kwargs)

    def serialize_relativedelta(self, rd):
        return json.dumps(rd.kwargs)
    def get_status_desc(self):
        
        next_date=f"<t:{int(self.next_run.timestamp())}:f>"
        auto_log_chan=f"<#{self.target_channel_id}>"
        output=f"Auto Log Channel:{auto_log_chan}\nNext Run Time:{next_date}"
        return output


    
