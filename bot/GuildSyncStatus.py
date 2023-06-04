import logging
import traceback
from typing import Any, Dict, List, Tuple, Union
from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, DateTime, Double
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import select, not_, func
import datetime
from assets import *
import gui

from discord.ext import commands
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
        addit = delit = False #
        for key in keys:
            val1 = dict1.get(key)
            val2 = dict2.get(key)
            if val1 != val2:
                #gui.gprint(same)
                if val2==None:
                    if not delit:
                        delit=True
                        diff['del']=[]
                    diff['del'].append(key)
                elif val1==None:
                    if not addit:
                        diff['add']=[]
                    diff['add'].append(key)
                else:
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
        Returns `True` if they are the same, `False` otherwise along with debug information
        """
        
        oldsync = (self.lastsyncdata)
        newsync = (json.dumps(command_tree, default=str))
        
        oldtree = json.loads(oldsync)
        newtree = json.loads(newsync)

        try:
            #This is preferrable to an API call.
            difference, same,total,simscore = dict_diff(oldtree, newtree)
            debug, score=f"Differences found: {difference}", f"{total-same} keys out of {total} are different, simularity is {round(simscore,2)}%"

            if same==total:
                score=f"All {total} keys are identical!"
                return True, debug, score
            return False, debug, score
            
        except Exception as e:
            gui.gprint(e)

        return oldsync == newsync, 0.0


def remove_null_values(dictionary):
    """
    Remove all null, empty, or false values from the parent dictionary each nested dictionary into the parent dictionary.
    This is to create a compressed output file for debugging.
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
def is_list_of_dicts(element):
    if isinstance(element, list) and all(isinstance(elem, dict) for elem in element):
        return True
    else:
        return False
def denest_dict(d: dict)->Dict[str, Any]:
    """
    Recursively denests a nested dictionary by merging each nested dictionary into the parent dictionary.
    This is to more easily compare which elements are different in dict_diff
    Parameters:
    d: A nested dictionary to be denested.

    Returns:
    A denested dictionary with each nested dictionary's key-value pairs merged into the parent dictionary.
    """
    out = {}
    for key, value in d.items():
        if isinstance(value, list) and all(isinstance(elem, dict) for elem in value):
            for dictv in value:
                name=dictv['name']
                out.update({f"{key}->{name}->{nested_key}": nested_value for nested_key, nested_value in denest_dict(dictv).items() if nested_key!='name'})
        elif isinstance(value, dict):
            out.update({f"{key}->{nested_key}": nested_value for nested_key, nested_value in denest_dict(value).items() if nested_key!='name'})
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
        current_command_list.append(command)
    while not to_walk.empty():
        group = to_walk.get()
        for i in group.walk_commands():
            if isinstance(i, discord.app_commands.Command):
                current_command_list.append(i)
            elif isinstance(i, discord.app_commands.Group):
                to_walk.put(i)

    return current_command_list

def build_and_format_app_commands(tree:discord.app_commands.CommandTree, guild=None, nestok=False, slimdown=False)->Dict[str, Any]:
    '''This function takes in a discord.app_commands.CommandTree,  converts
    each Command, Group, and ContextMenu into a dictionary with the to_dict function,
      and reformats the dictionary in such a way that each 
    dictionary is guaranteed to be the same between generations.
    Equivalent to calling build_app_command_list then format_application_commands, however instead of
    O(2n), it's simply O(n)
    
    Parameters:
    tree: a CommandTree instance

    Returns:
    Dictionary of serialized attributes from app commands.
    '''
    formatted_commands = {
        'chat_commands':{},
        'context_user':{},
        'context_message':{}
    }

    for command in tree.get_commands(guild=guild):
        di=command.to_dict() #I really wish this was in the docs...
        typev,name=di['type'],di['name']
        typestr='chat_commands'
        if typev==2:
            typestr='context_user'
        elif typev==3:
            typestr='context_message'
        formatted_commands[typestr][name]=di
    den=formatted_commands
    if slimdown:
        den=remove_null_values(den)
    if not nestok:
        den=denest_dict(formatted_commands)
    return den

def format_parameters(parameters:List[discord.app_commands.Parameter])->Dict[str,Any]:
    '''DEPRECATED
    Serialize a list of parameters into a dictionary, and return it.'''
    params={}
    for parameter in parameters:
        param_name=str(parameter.name)
        formatted_parameter = {
            'name': param_name,
            'display_name': str(parameter.display_name),
            'description': parameter.description if parameter.description is not discord.utils.MISSING else None,
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


def format_one_command(command:Union[discord.app_commands.Command,discord.app_commands.ContextMenu]):
    '''DEPRECATED'''
    if isinstance(command,discord.app_commands.Command):
        #Serializing a Command
        formatted_command = {
            'name': command.name,
            'description': command.description if command.description is not discord.utils.MISSING else None,
            'parameters': format_parameters(command.parameters),
            'permissions': {
                'default_permissions': command.default_permissions.value if command.default_permissions is not None else None,
                'guild_only': command.guild_only,
                'nsfw': command.nsfw
            }
        }
        parents=[]
        if command.parent:
            parent=command.parent
            parents.append(parent.name)
            if parent.parent:
                parent=parent.parent
                parents.append(parent.name)
                #Discord does not allow you to go deeper than this.
        
        return 'chat_commands',formatted_command, parents


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
        typestr='context_message'
        if command.type==discord.AppCommandType.user:
            typestr= 'context_user'
        return typestr, formatted_command,[]
            
def format_application_commands(commands:List[Union[discord.app_commands.Command,discord.app_commands.Group,discord.app_commands.ContextMenu]], nestok=False, slimdown=False)->Dict[str, Any]:
    '''This function takes in a list of discord.app_commands Command, Group, and ContextMenu objects, converts
    each into a dictionary with the to_dict function, and reformats the dictionary in such a way that each 
    dictionary is guaranteed to be the same between generations.
    
    Parameters:
    commands: List of application commands.
    nestok: if this function should return a nested dictionary, default False
    slimdown: if this function should not include false, null, or empty values in the returned dictionary, default False
    Returns:
    Dictionary of serialized attributes from commands.
    '''
    formatted_commands = {
        'chat_commands':{},
        'context_user':{},
        'context_message':{}
    }
    for command in commands:
        di=command.to_dict() #I really wish this was in the docs...
        typev,name=di['type'],di['name']
        typestr='chat_commands'
        if typev==2:
            typestr='context_user'
        elif typev==3:
            typestr='context_message'
        formatted_commands[typestr][name]=di
        # command_type, formatted_command, parents=format_one_command(command)
        # current_dict=formatted_commands[command_type]
        # for parent in parents:
        #     current_dict.setdefault(parent, {})
        #     current_dict = current_dict[parent]
        # current_dict[command.name] = formatted_command

    den=formatted_commands
    if slimdown:
        den=remove_null_values(den)
    if not nestok:
        den=denest_dict(formatted_commands)
    #for i, v in den.items(): gui.gprint(i,v)
    return den


class SpecialAppSync:
    '''Mixin that defines custom syncing logic.'''
    
    async def sync_commands_tree(self, guild:discord.Guild, forced=False):
        '''Build a dictionary representation of all app commands to be synced, check if 
        the dictionary is different from a loaded version from before, and then 
        sync the commands tree for the given guild, updating the dictionary.'''
        gui.gprint(f"Checking if it's time to sync commands for {guild.name} (ID {guild.id})...")
        try:
            #SQLAlchemy is used to handle database connections.
            #synced=build_app_command_list(self.tree,guild)
            app_tree=build_and_format_app_commands(self.tree,guild)
            dbentry:AppGuildTreeSync=AppGuildTreeSync.get(guild.id)
            if not dbentry:
                dbentry=AppGuildTreeSync.add(guild.id)
            same, diffscore,score=dbentry.compare_with_command_tree(app_tree)
            gui.gprint(f"Check Results: {guild.name} (ID {guild.id}):{score}")
            self.logs.info(f"Check Results: {guild.name} (ID {guild.id}):\n differences{diffscore} \n{score}")
            #Check if it's time to edit
            if (not same) or forced==True:
                gui.gprint(f"Updating serialized command tree for {guild.name} (ID {guild.id})...")
                dbentry.update(app_tree)
                same,diffscore,score=dbentry.compare_with_command_tree(app_tree)
                gui.gprint(f"Starting sync for {guild.name} (ID {guild.id})...")
                await self.tree.sync(guild=guild)
                gui.gprint(f"Sync complete for {guild.name} (ID {guild.id})...")
        except Exception as e:
            gui.gprint(str(e))
            res=str(traceback.format_exception(None, e, e.__traceback__))
            gui.gprint(res)

    async def sync_enabled_cogs_for_guild(self,guild, force=False):
        '''With a passed in guild, sync all activated cogs for that guild.
        Works on a guild per guild basis in case I need to eventually provide
        code to sync different app commands between guilds.'''
        def syncprint(*lis):
            pass
            if False:  gui.gprint(f"Sync for {guild.name} (ID {guild.id})",*lis)
        def should_skip_cog(cogname: str) -> bool:
            """Determine whether a cog should be skipped during synchronization."""
            '''Not currently needed.'''
            return False

        def add_command_to_tree(command, guild):
            #Add a command to the command tree for the given guild.
            if command.extras:
                if command.extras.get("homeonly"):
                    gui.gprint("yes")
                    if guild.id!=int(AssetLookup.get_asset('homeguild')):
                        return 
            if isinstance(command, (commands.HybridCommand, commands.HybridGroup)):
                try:
                    self.tree.add_command(command.app_command, guild=guild, override=True)
                    syncprint(f"Added hybrid {command.name}")
                except:
                    syncprint(f"Cannot add {command.name}, case error.")
            else:
                try:
                    self.tree.add_command(command, guild=guild, override=True)
                    syncprint(f"Added {command.name}")
                except:
                    syncprint(f"Cannot add {command.name}, this is not a app command")


        #Gather all activated cogs for a given guild.
        #Note, the reason it goes one by one is because it was originally intended 
        #to activate/deactivate cogs on a server per server basis.        
        for cogname, cog in self.cogs.items():
            if should_skip_cog(cogname):
                gui.gprint("skipping cog ",cogname)
                continue
            if hasattr(cog,'ctx_menus'):
                for name,cmenu in cog.ctx_menus.items():
                    self.tree.add_command(cmenu, guild=guild, override=True)
            for command in cog.walk_commands():
                add_command_to_tree(command, guild)
            for command in cog.walk_app_commands():
                add_command_to_tree(command, guild)

        


    async def all_guild_startup(self, force=False,sync_only=False, no_sync=False):
        '''fetch all available guilds, and sync the command tree.'''
        try:
            gui.gprint(self.guilds)
            async for guild in self.fetch_guilds(limit=10000):
                gui.gprint(f"syncing for {guild.name}")
                if not sync_only:
                    await self.sync_enabled_cogs_for_guild(guild,force=force)
                if no_sync==False or sync_only:
                    await self.sync_commands_tree(guild, forced=force)
        except Exception as e:
            gui.gprint(e)
            raise Exception()
        
    async def get_tree_dict(self,guild):
        app_tree=build_and_format_app_commands(self.tree,guild,nestok=True, slimdown=True)
        return app_tree
    