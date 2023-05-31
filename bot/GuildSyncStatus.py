import logging
from typing import Any, Dict, List, Tuple, Union
from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, DateTime, Double
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import select, not_, func
import datetime

from database import DatabaseSingleton
from queue import Queue

Guild_Sync_Base = declarative_base()

import json
import discord
'''
All the convienence of automatic command syncing with fewer drawbacks.
During a sync, format_application_commands will take in a list of AppCommand.Command objects, 
and create a dictionary of the serialized attributes of AppCommand.Command.

'''

from collections.abc import Mapping


logger=logging.getLogger("TCLogger")
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
        same = total= max(len(keys),1)
        diff = {}
        for key in keys:
            val1 = dict1.get(key)
            val2 = dict2.get(key)
            if val1 != val2:
                #print(same)
                diff[key] = (val1, val2)
                same-=1
        samescore=same/total
        if diff:
            return diff, same,total,samescore*100.0
        return None, same,total,samescore*100.0
    elif dict1 != dict2:
        return (dict1, dict2), 0,1,0.0
    return None, 1,1,100.0

class AppGuildTreeSync(Guild_Sync_Base):
    '''table to store serialized command trees to help with the autosync system.'''
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

    def compare_with_command_tree(self, command_tree: dict) -> Tuple[bool,str,str]:
        """
        Compares the current `lastsyncdata` with a passed in `command_tree`.
        Returns `True` if they are the same, `False` otherwise along with a 'simularity score.'
        """
        
        oldsync = (self.lastsyncdata)
        newsync = (json.dumps(command_tree, default=str))
        
        oldtree = json.loads(oldsync)
        newtree = json.loads(newsync)

        try:
            #This is preferrable to an API call.
            difference, same,total,simscore = dict_diff(oldtree, newtree)
            debug, score=f"Differences found: {difference}", f"All {total} are identical!"

            if difference==None:
                score=f"{total-same} keys out of {total} are different, simularity is {round(simscore,2)}%"
                return True, debug, score
            return False, debug, score
            
        except Exception as e:
            print(e)

        return oldsync == newsync, 0.0


def remove_null_values(dictionary):
    """
    Remove all null, empty, or false values from the parent dictionary each nested dictionary into the parent dictionary.
    This is to more easily check nested elements.
    Parameters:
    d: A nested dictionary to be cleared.

    Returns:
    A nested dictionary with all empty values eliminated.
    """
    new_dict = {}
    for key, value in dictionary.items():
        if isinstance(value, dict):
            new_value = remove_null_values(value)
            if new_value:
                new_dict[key] = new_value
        elif value==discord.utils.MISSING:
            pass
        elif value is not None and value != "" and value is not False and value !=[]:
            new_dict[key] = value
    return new_dict

def denest_dict(d: dict)->Dict[str, Any]:
    """
    Recursively denests a nested dictionary by merging each nested dictionary into the parent dictionary.
    This is to more easily check nested elements.
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

def build_app_command_list(tree:discord.app_commands.CommandTree, guild=None)->List[discord.app_commands.Command]:
    '''This function takes in a discord.app_commands.CommandTree objects, and
    extracts each app command into a list so that format_application_commands may be used.
    
    Parameters:
    tree: a CommandTree instance

    Returns:
    List of discord.app_commands.Command objects.
    '''
    current_command_list=[]
    to_walk= Queue()
    for command in tree.get_commands(guild=guild):
        if isinstance(command,discord.app_commands.Group):
            to_walk.put(command)
        else:
            current_command_list.append(command)
    while not to_walk.empty():
        group = to_walk.get()
        for i in group.walk_commands():
            if isinstance(i, discord.app_commands.Command):
                current_command_list.append(i)
            elif isinstance(i, discord.app_commands.Group):
                to_walk.put(i)

    return current_command_list


def format_parameters(parameters:List[discord.app_commands.Parameter])->Dict[str,Any]:
    '''Serialize all parameter attributes into a dictionary.'''
    params={}
    for parameter in parameters:
        param_name=str(parameter.name)
        formatted_parameter = {
            'name': param_name,
            'display_name': str(parameter.display_name),
            'description': str(parameter.description),
            'type': parameter.type.name,
            'choices': {
                str(c.name): 
                {'name': c.name, 'value': c.value} for c in parameter.choices},
            'channel_types': [channel_type.name for channel_type in parameter.channel_types],
            'required': parameter.required,
            'autocomplete': parameter.autocomplete,
            'min_value': parameter.min_value,
            'max_value': parameter.max_value,
            'default': parameter.default if parameter.default is not discord.utils.MISSING else None
        }
        params[param_name]=formatted_parameter
    return params

def format_application_commands(commands:List[Union[discord.app_commands.Command,discord.app_commands.ContextMenu]], nestok=False, slimdown=False)->Dict[str, Any]:
    '''This function takes in a list of discord.app_commands.Command objects, and
    extracts serializable data into a dictionary to help determine if a app command tree
    should be synced to a particular server or not.
    
    Parameters:
    commands: List of application commands.
    nestok: if this function should return a nested dictionary, default False
    slimdown: if this function should not include false, null, or empty values in the returned dictionary, default False
    Returns:
    Dictionary of serialized attributes from commands.
    '''
    formatted_commands = {
        'chat':{},
        'context_user':{},
        'context_message':{}
    }
    for command in commands:
        if isinstance(command,discord.app_commands.Command):
            #Serializing a Command
            formatted_command = {
                'name': command.name,
                'description': command.description,
                'parameters': format_parameters(command.parameters),
                'permissions': {
                    'default_permissions': command.default_permissions.value if command.default_permissions is not None else None,
                    'guild_only': command.guild_only,
                    'nsfw': command.nsfw
                }
            }
            if command.parent:
                if not str(command.parent.name) in formatted_commands['chat']:
                    formatted_commands['chat'][str(command.parent.name)]={}
                formatted_commands['chat'][str(command.parent.name)][command.name] = formatted_command
            else:
                formatted_commands['chat'][command.name] = formatted_command

        else:
            #Serializing a ContextMenu
            formatted_command = {
                'name': command.name,
                'permissions': {
                    'default_permissions': command.default_permissions.value if command.default_permissions is not None else None,
                    'guild_only': command.guild_only,
                    'nsfw': command.nsfw
                },
                'type': str(command.type)
            }
            if command.type==discord.AppCommandType.message:
                formatted_commands['context_message'][command.name] = formatted_command
            if command.type==discord.AppCommandType.user:
                formatted_commands['context_user'][command.name] = formatted_command
    den=formatted_commands
    if slimdown:
        den=remove_null_values(den)
    if not nestok:
        den=denest_dict(formatted_commands)
    return den
