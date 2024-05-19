from .helldive import *
import datetime
import numpy as np
import csv
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
    __slots__=['client','max_list_size','war','campaigns','assignments','planets','dispatches','last_planet_get']
    def __init__(self,client:APIConfig=APIConfig(),max_list_size=8):
        self.client=client
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
        print(self.client)
        war=campaigns=assignments=dispatches=None
        try:
            war=await GetApiV1War(api_config_override=self.client)
            assignments=await GetApiV1AssignmentsAll(api_config_override=self.client)
            campaigns=await GetApiV1CampaignsAll(api_config_override=self.client)
            dispatches=await GetApiV1DispatchesAll(api_config_override=self.client)
        except Exception as e:
            raise e

        if dispatches is not None:
            self.dispatches=dispatches

        if war is not None:
            self.war.add(war)
        if assignments is not None:
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
        if campaigns is not None:
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


def add_to_csv(stat:ApiStatus,hdtext={}):
    # Get the first change in the war statistics
    war, lastwar = stat.war.get_first_change()
    mp_mult = war.impactMultiplier
    
    # Prepare a list to hold the rows to be written to the CSV
    rows = []
    timestamp=int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
    # Iterate through the campaigns to gather statistics
    for k, campaign_list in stat.campaigns.items():
        if len(campaign_list) <= 1:
            print(f"{timestamp} {k} not enough campaigns.")
            continue
        
        camp, last = campaign_list.get_first_change()
        players = camp.planet.statistics.playerCount
        
        change = camp - last
        decay = camp.planet.regenPerSecond
        total_sec = change.planet.retrieved_at.total_seconds()
        damage = (change.planet.health / total_sec)*-1
        evt_damage=None
        mode=1
        if change.planet.event:
            evt_damage=(change.planet.event.health / total_sec)*-1
        if damage<=0:
            if not evt_damage:
                print("Damage too low!")
                continue
            if evt_damage<=0:
                print("Event Damage too low!")
                continue
            else:
                mode=2
                eps = (evt_damage) / mp_mult
                decay=0
        else:
            eps = (damage + decay) / mp_mult
        
        stats = change.planet.statistics
        wins = stats.missionsWon / total_sec
        loss = stats.missionsLost / total_sec
        kills = (stats.automatonKills + stats.terminidKills + stats.illuminateKills) / total_sec
        deaths = stats.deaths / total_sec
        
        # Prepare the row for the CSV
        row = {
            'timestamp': timestamp,
            'player_count': players,
            'mode':mode,
            'mp_mult': mp_mult,
            'wins_per_sec': wins,
            'loss_per_sec': loss,
            'decay_rate': decay,
            'kills_per_sec': kills,
            'deaths_per_sec': deaths,
            'eps': eps
        }
        
        # Append the row to the list of rows
        rows.append(row)
    
    # Define the CSV file path
    csv_file_path = 'statistics.csv'
    
    # Write the rows to the CSV file
    print(rows)
    if not rows:
        return
    with open(csv_file_path, mode='a', newline='',encoding='utf8') as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        
        # If the file is empty, write the header
        if file.tell() == 0:
            writer.writeheader()
        
        # Write the rows
        for row in rows:
            writer.writerow(row)