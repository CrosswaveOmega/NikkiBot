import difflib
from typing import List, Union
from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, DateTime, Double
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import select, not_, func
import datetime

from database import DatabaseSingleton

Guild_Sync_Base = declarative_base()

import json
import discord
import difflib
'''
All the convienence of automatic command syncing with fewer drawbacks.
During a sync, format_application_commands will take in a list of AppCommand.Command objects, 
and create a dictionary of the serialized attributes of AppCommand.Command.

'''

from collections.abc import Mapping



def dict_diff_recursive(dict1, dict2):
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
                    nested_diff = dict_diff_recursive(val1, val2)
                    if nested_diff:
                        diff[key] = nested_diff
                else:
                    diff[key] = (val1, val2)
        if diff:
            return diff

    elif dict1 != dict2:
        return (dict1, dict2)

    return None

def dict_diff(dict1, dict2):
    """
    Iteratively compare two non-nested dictionaries and return the differences.
    This is for debugging.
    """
    if isinstance(dict1, Mapping) and isinstance(dict2, Mapping):

        keys = set(list(dict1.keys()) + list(dict2.keys()))
        same=total= max(len(keys),1)
        diff = {}
        for key in keys:
            val1 = dict1.get(key)
            val2 = dict2.get(key)
            if val1 != val2:
                print(same)
                diff[key] = (val1, val2)
                same-=1
        samescore=same/total
        if diff:
            return diff, samescore*100.0
        return None, samescore*100.0


    elif dict1 != dict2:
        return (dict1, dict2), 0.0

    return None, 100.0
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
            difference, simscore = dict_diff(arr1, arr2)
            print(f"Differences found: {difference}\n simularity score:{round(simscore,1)}")
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

def denest_dict(d: dict) -> dict:
    """
    Recursively denests a nested dictionary by merging each nested dictionary into the parent dictionary.

    Parameters:
    d: A nested dictionary to be denested.

    Returns:
    A denested dictionary with each nested dictionary's key-value pairs merged into the parent dictionary.
    """
    out = {}
    for key, value in d.items():
        if isinstance(value, dict):
            out.update({f"{key}->{nested_key}": nested_value for nested_key, nested_value in denest_dict(value).items()})
        else:
            out[key] = value
    return out
def format_application_commands(commands:List[discord.app_commands.Command]):
    '''This command takes in a list of discord.app_commands.Command objects, and
    extracts serializable data into a dictionary to help determine if a app command tree
    should be synced to a particular server or not.
    '''
    formatted_commands = {}
    for command in commands:
        
        formatted_command = {
            'name': command.name,
            'description': command.description,
            'parameters': {},
            'permissions': {}
        }
        #print(command.name)
        for parameter in command.parameters:
            formatted_parameter = {
                'name': str(parameter.name),
                'display_name': str(parameter.display_name),
                'description': str(parameter.description),
                'type': parameter.type.name,
                'choices': {},
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
                formatted_parameter['choices'][str(choice.name)]=(formatted_choice)

            for channel_type in parameter.channel_types:
                formatted_parameter['channel_types'].append(channel_type.name)

            formatted_command['parameters'][str(parameter.name)]=(formatted_parameter)

        if command.default_permissions is not None:
            formatted_command['permissions']['default_permissions'] = command.default_permissions.value

        formatted_command['permissions']['guild_only'] = command.guild_only
        formatted_command['permissions']['nsfw'] = command.nsfw

        formatted_commands[command.name]=(formatted_command)
    den=denest_dict(formatted_commands)
    return den
