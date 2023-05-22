from typing import Any, Dict, List
import discord
import random



class TC_Cog_Mixin:
    '''A mixin to define an additional function.'''
    def server_profile_field_ext(self, guild:discord.Guild)-> Dict[str, Any]:
        '''returns a dictionary that represents a single discord embed field
        with 3 key/value pairs:  name:str.  value:str.  inline:boolean'''
        return {}

class CogFieldList:
    '''This is mixed into the TCBot object'''
    def get_field_list(self, guild:discord.Guild)-> List[Dict[str, Any]]:
        '''returns a list of dictionaries that represents a single discord embed field
        with 3 key/value pairs:  name:str.  value:str.  inline:boolean'''
        cogs_list = self.cogs.values()
        extended_fields=[]
        # Add extended fields
        for cog in cogs_list:
            if hasattr(cog, 'server_profile_field_ext') and callable(getattr(cog, 'server_profile_field_ext')):
                res=cog.server_profile_field_ext(guild)
                if res:
                    extended_fields.append(res)
                print(f"{cog.__class__.__name__} has the function 'server_profile_fieldext'")
            else: pass
        return extended_fields

class StatusTicker:
    '''Mixin that provides rotating bot statuses.'''
    status_map,status_queue={},[]

    def add_act(self,key:str, value:str, activity_type:discord.ActivityType=discord.ActivityType.playing):
        """Add an activity to the status map.
        Args:
            key (str): Key of status. 
            value (str): status to be displayed.
            activity_type (discord.ActivityType, optional): The type of status to be displayed.
        """        
        activity = discord.Activity(type=activity_type, name=value)
        self.status_map[key] = activity

    def remove_act(self,key):
        """Add an activity to the status map.
        Args:
            key (str): Key of status. 
            value (str): status to be displayed.
            activity_type (discord.ActivityType, optional): The type of status to be displayed.
        """     
        if key in self.status_map:
            self.status_map.pop(key)


    async def status_ticker_next(self):
        '''select the next relevant status element.'''
        if self.status_map:
            if not self.status_queue:
                self.status_queue= list(self.status_map.keys())
                random.shuffle(self.status_queue)
            cont=True
            while cont and len(self.status_queue)>=1:
                cont=False
                if len(self.status_queue)>=1:
                    key=self.status_queue.pop(0)
                    if key in self.status_map:
                        status=self.status_map[key]
                        await self.change_presence(activity=status)
                    else: cont=True