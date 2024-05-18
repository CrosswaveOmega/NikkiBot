from .helldive import *
import datetime
class LimitedSizeList(list):
    def __init__(self, max_size):
        self.max_size = max_size
        self.items:List[Union[War,Assignment2,Campaign2]] = []

    def add(self, item):
        if len(self.items) >= self.max_size:
            self.items.pop()
        self.items.insert(0,item)

    def get_changes(self)->List[Union[War,Assignment2,Campaign2]] :
        '''return a list of all differences between items in this limited sized list.'''
        curr,this=None,[]
        for i in self.items:
            if curr is None:
                curr=i
            else:
                this.append(i-curr)
                curr=i
        return this
    
    def get_first_change(self):
        if len(self.items)>1:
            return (self.items[0],self.items[1])
        return self.items[0], self.items[0]

    def __repr__(self):
        return repr(self.items)

    def __len__(self):
        return len(self.items)


class ApiStatus:
    """
    A container class for information retrieved from Helldivers 2's api.
    """
    __slots__=['max_list_size','war','campaigns','assignments','planets','dispatches','last_planet_get']
    def __init__(self,max_list_size=8):
        self.max_list_size=max_list_size
        self.war:LimitedSizeList[War]=LimitedSizeList(self.max_list_size)
        self.assignments:Dict[int,LimitedSizeList[Assignment2]]={}
        self.campaigns:Dict[int,LimitedSizeList[Campaign2]]={}
        self.planets:Dict[int,Planet]={}
        self.dispatches:List[Dispatch]=[]
        self.last_planet_get:datetime.datetime=datetime.datetime(2024,1,1,0,0,0)

    async def update_data(self):
        '''
        Query the community api, and load the data into the classes.
        '''
        war=await GetApiV1War()
        assignments=await GetApiV1AssignmentsAll()
        campaigns=await GetApiV1CampaignsAll()
        dispatches=await GetApiV1DispatchesAll()
        self.dispatches=dispatches
        self.war.add(war)
        assign_ids=set()
        for a in assignments:
            assign_ids.add(a.id)
            if a.id not in self.assignments:
                self.assignments[a.id]=LimitedSizeList(self.max_list_size)
            self.assignments[a.id].add(a)
        key_list=list(self.assignments.keys())
        for k in key_list:
            if k not in assign_ids:
                print(f"removing assignment {k}")
                self.assignments.pop(k)
        camp_ids=set()
        for c in campaigns:
            camp_ids.add(c.id)
            if c.id not in self.campaigns:
                self.campaigns[c.id]=LimitedSizeList(self.max_list_size)
            self.campaigns[c.id].add(c)
        key_list=list(self.campaigns.keys())
        for k in key_list:
            if k not in camp_ids:
                print(f"removing campaign {k}")
                self.campaigns.pop(k)
        if datetime.datetime.now() >= self.last_planet_get + datetime.timedelta(hours=2):
            planets=await GetApiV1PlanetsAll()
            planet_data={}
            for planet in planets:
                planet_data[planet.index]=planet
            self.planets=planet_data
            self.last_planet_get = datetime.datetime.now()
