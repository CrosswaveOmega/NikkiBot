import datetime
from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .Biome import Biome
from .Event import Event
from .Hazard import Hazard
from .Position import Position
from .Statistics import Statistics

from utility import human_format as hf, select_emoji as emj, changeformatif as cfi, extract_timestamp as et
from discord.utils import format_dt as fdt

class Planet(BaseApiModel):
    """
    None model
        Contains all aggregated information AH has about a planet.

    """

    index: Optional[int] = Field(alias="index", default=None)

    name: Optional[Union[str, Dict[str, Any]]] = Field(alias="name", default=None)

    sector: Optional[str] = Field(alias="sector", default=None)

    biome: Optional[Biome] = Field(alias="biome", default=None)

    hazards: Optional[List[Optional[Hazard]]] = Field(alias="hazards", default=None)

    hash: Optional[int] = Field(alias="hash", default=None)

    position: Optional[Position] = Field(alias="position", default=None)

    waypoints: Optional[List[int]] = Field(alias="waypoints", default=None)

    maxHealth: Optional[int] = Field(alias="maxHealth", default=None)

    health: Optional[int] = Field(alias="health", default=None)

    disabled: Optional[bool] = Field(alias="disabled", default=None)

    initialOwner: Optional[str] = Field(alias="initialOwner", default=None)

    currentOwner: Optional[str] = Field(alias="currentOwner", default=None)

    regenPerSecond: Optional[float] = Field(alias="regenPerSecond", default=None)

    event: Optional[Event] = Field(alias="event", default=None)

    statistics: Optional[Statistics] = Field(alias="statistics", default=None)

    attacking: Optional[List[int]] = Field(alias="attacking", default=None)

    def __sub__(self, other: "Planet") -> "Planet":
        # Calculate the values for health, statistics, and event based on subtraction
        new_health = self.health - other.health if self.health is not None and other.health is not None else None
        new_statistics = self.statistics - other.statistics if self.statistics is not None and other.statistics is not None else None
        new_event = self.event - other.event if self.event is not None and other.event is not None else self.event

        # Create a new instance of the Planet class with calculated values
        planet= Planet(
            health=new_health,
            statistics=new_statistics,
            event=new_event,
            index=self.index,
            name=self.name,
            sector=self.sector,
            biome=self.biome,
            hazards=self.hazards,
            hash=self.hash,
            position=self.position,
            waypoints=self.waypoints,
            maxHealth=self.maxHealth,
            disabled=self.disabled,
            initialOwner=self.initialOwner,
            currentOwner=self.currentOwner,
            regenPerSecond=self.regenPerSecond,
            attacking=self.attacking,
        )
        planet.retrieved_at=self.retrieved_at-other.retrieved_at
        return planet

    
    def estimate_remaining_lib_time(self, diff:'Planet'):
        time_elapsed=diff.retrieved_at
        if time_elapsed.total_seconds()==0:
            return f""
        change=diff.health/time_elapsed.total_seconds()
        if change==0:
            if self.currentOwner.lower()!='humans':
                return f"Stalemate."
            return ""
        if change>0:
            return "Losing."
        estimated_seconds=abs(self.health/change)
        timeval= self.retrieved_at+datetime.timedelta(seconds=estimated_seconds)
        return f"{round(change,5)},{fdt(timeval,'R')}"
        pass

    @staticmethod
    def average(planets_list: List['Planet']) -> 'Planet':
        count = len(planets_list)
        if count == 0:
            return Planet()
        
        avg_health = sum(planet.health for planet in planets_list if planet.health is not None) // count
        avg_statistics = Statistics.average([planet.statistics for planet in planets_list if planet.statistics is not None])
        avg_event = Event.average([planet.event for planet in planets_list if planet.event is not None])

        avg_time=  sum(planet.retrieved_at.total_seconds() for planet in planets_list if planet.retrieved_at is not None) // count
        avg_planet = Planet(
            health=avg_health,
            statistics=avg_statistics,
            event=avg_event,
            index=planets_list[0].index,
            name=planets_list[0].name,
            sector=planets_list[0].sector,
            hash=planets_list[0].hash,
            waypoints=planets_list[0].waypoints,
            maxHealth=planets_list[0].maxHealth,
            disabled=planets_list[0].disabled,
            initialOwner=planets_list[0].initialOwner,
            currentOwner=planets_list[0].currentOwner,
            regenPerSecond=planets_list[0].regenPerSecond,
            attacking=planets_list[0].attacking,
        )
        avg_planet.retrieved_at=datetime.timedelta(seconds=avg_time)
        return avg_planet
    
    def campaign_against(self)->str:
        '''Get the emoji of the faction that is occupying or defending this planet.'''
        faction=emj(self.currentOwner.lower())
        if self.event:
            evt=self.event
            return emj(self.event.faction.lower())
        return faction
    
    def simple_planet_view(self,prev:Optional['Planet']=None,avg:Optional['Planet']=None)->Tuple[str,str]:
        """Return a string containing the formated state of the planet.

        Args:
            prev (Optional[&#39;Planet&#39;], optional): 
            avg (Optional[&#39;Planet&#39;], optional):Average stats for the past X planets

        Returns:
            Tuple[str,str]: _description_
        """
        diff=self-self
        if prev is not None: 
            diff=prev
        
        faction=emj(self.currentOwner.lower())
        
        name=f"{faction}P#{self.index}: {self.name}"
        players=f"{emj('hdi')}: `{self.statistics.playerCount} {cfi(diff.statistics.playerCount)}`"
        out=f"{players}\nHealth {round((self.health/self.maxHealth)*100.0,5)}% {cfi(round((diff.health/self.maxHealth)*100.0,5))}"
        if avg:
            remaining_time=self.estimate_remaining_lib_time(avg)
            out+="\n"+remaining_time
        if self.event:
            evt=self.event
            timev=fdt(et(evt.endTime),'R')
            event_fact=emj(self.event.faction.lower())
            #, {evt.health}{cfi(diff.event.health)}/{evt.maxHealth}.
            out+=f"\n Time limit:{timev} Defend from {event_fact} \n Lib {round((evt.health/evt.maxHealth)*100.0, 5)}% {cfi(round((diff.event.health/evt.maxHealth)*100.0, 5))}"
            if avg:
                if avg.event:
                    out+=f"\n {self.event.estimate_remaining_lib_time(avg.event)}"

        return name,out


