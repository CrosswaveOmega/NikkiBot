import difflib
from typing import Union
from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, DateTime, Double
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import select, not_, func
import datetime

from database import DatabaseSingleton

Guild_Sync_Base = declarative_base()

import json

import difflib
'''
All the convienence of automatic command syncing with fewer drawbacks.

'''

from collections.abc import Mapping



def dict_diff(dict1, dict2):
    """
    Recursively compare two dictionaries and return the differences.
    This is for debugging.
    """
    if isinstance(dict1, Mapping) and isinstance(dict2, Mapping):

        keys = set(list(dict1.keys()) + list(dict2.keys()))

        diff = {}
        for key in keys:
            val1 = dict1.get(key)
            val2 = dict2.get(key)
            if val1 != val2:
                if isinstance(val1, Mapping) and isinstance(val2, Mapping):
                    nested_diff = dict_diff(val1, val2)
                    if nested_diff:
                        diff[key] = nested_diff
                else:
                    diff[key] = (val1, val2)
        if diff:
            return diff

    elif dict1 != dict2:
        return (dict1, dict2)

    return None

class AppGuildTreeSync(Guild_Sync_Base):
    '''table to store data for Automatic guild tasks.'''
    __tablename__ = 'apptree_guild_sync'
    server_id = Column(Integer, primary_key=True, nullable=False, unique=True)
    lastsyncdata = Column(Text, nullable=True)
    lastsyncdate = Column(DateTime, default=datetime.datetime.utcnow())

    def __init__(self, server_id: int, command_tree: dict=None):
        self.server_id = server_id
        self.lastsyncdata = json.dumps(command_tree,default=str)
        self.lastsyncdate=datetime.datetime.utcnow()

    @classmethod
    def get(cls, server_id):
        """
        Returns the entire AppGuildTreeSync entry for the specified server_id, or None if it doesn't exist.
        """
        session:Session = DatabaseSingleton.get_session()
        result = session.query(AppGuildTreeSync).filter_by(server_id=server_id).first()
        if result:            
            return result
        else:            
            return None
    @classmethod
    def add(cls, server_id):
        """
        Add a new AppGuildTreeSync entry for the specified server_id.
        """
        toAdd=AppGuildTreeSync(server_id)
        session:Session = DatabaseSingleton.get_session()
        session.add(toAdd)
        session.commit()
        return toAdd
    def update(self, command_tree: dict):
        """
        Updates the `lastsyncdata` attribute of the current `AppGuildTreeSync` instance with a new serialized
        command tree, or creates a new entry if one doesn't exist for the current `server_id`.
        """
        session:Session = DatabaseSingleton.get_session()
        self.lastsyncdata = json.dumps(command_tree, default=str)
        self.lastsyncdate=datetime.datetime.utcnow()
        session.commit()

    def compare_with_command_tree(self, command_tree: dict) -> bool:
        """
        Compares the current `lastsyncdata` with a passed in `command_tree`.
        Returns `True` if they are the same, `False` otherwise.
        """
        
        string1 = (self.lastsyncdata)
        string2 = (json.dumps(command_tree, default=str))
        
        arr1 = json.loads(string1)
        arr2 = json.loads(string2)

        try:
            #This is preferrable to an API call.
            difference = dict_diff(arr1, arr2)
            print(f"Differences found: {difference}")
            if difference==None:
                return True
            return False
            
        except Exception as e:
            print(e)

        return string1 == string2

def remove_null_values(dict_obj):
    #There's probably a better way.
    new_dictionary={}
    for key, value in list(dict_obj.items()):
        if value is not None:
            new_dictionary[key]=value
        elif isinstance(value, list):
            if value:
                new_dictionary[key]=value
        elif isinstance(value, dict):
            if value:
                new_dictionary[key]=value

    return new_dictionary

def format_application_commands(commands):
    formatted_commands = {}
    for command in commands:
        formatted_command = {
            'name': command.name,
            'description': command.description,
            'parameters': [],
            'permissions': {}
        }
        #print(command.name)
        for parameter in command.parameters:
            formatted_parameter = {
                'name': str(parameter.name),
                'display_name': str(parameter.display_name),
                'description': str(parameter.description),
                'type': parameter.type.name,
                'choices': [],
                'channel_types': [],
                'required': parameter.required,
                'autocomplete': parameter.autocomplete,
                'min_value': parameter.min_value,
                'max_value': parameter.max_value,
                'default': parameter.default
            }
            for choice in parameter.choices:
                formatted_choice = {
                    'name': choice.name,
                    'value': choice.value
                }
                formatted_parameter['choices'].append(formatted_choice)

            for channel_type in parameter.channel_types:
                formatted_parameter['channel_types'].append(channel_type.name)

            formatted_command['parameters'].append(formatted_parameter)

        if command.default_permissions is not None:
            formatted_command['permissions']['default_permissions'] = command.default_permissions.value

        formatted_command['permissions']['guild_only'] = command.guild_only
        formatted_command['permissions']['nsfw'] = command.nsfw

        formatted_commands[command.name]=(formatted_command)
    return formatted_commands
