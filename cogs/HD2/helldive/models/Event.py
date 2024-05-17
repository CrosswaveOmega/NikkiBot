from typing import *
import datetime
from pydantic import Field
from .ABC.model import BaseApiModel


from utility import human_format as hf, select_emoji as emj, changeformatif as cfi, extract_timestamp as et
from discord.utils import format_dt as fdt

class Event(BaseApiModel):
    """
    None model
        An ongoing event on a Planet.

    """

    id: Optional[int] = Field(alias="id", default=None)

    eventType: Optional[int] = Field(alias="eventType", default=None)

    faction: Optional[str] = Field(alias="faction", default=None)

    health: Optional[int] = Field(alias="health", default=None)

    maxHealth: Optional[int] = Field(alias="maxHealth", default=None)

    startTime: Optional[str] = Field(alias="startTime", default=None)

    endTime: Optional[str] = Field(alias="endTime", default=None)

    campaignId: Optional[int] = Field(alias="campaignId", default=None)

    jointOperationIds: Optional[List[int]] = Field(alias="jointOperationIds", default=None)

    def __sub__(self, other: "Event") -> "Event":
        new_health = self.health - other.health if self.health is not None and other.health is not None else None
        event= Event(
            id=self.id,
            eventType=self.eventType,
            faction=self.faction,
            health=new_health,
            maxHealth=self.maxHealth,
            startTime=self.startTime,
            endTime=self.endTime,
            campaignId=self.campaignId,
            jointOperationIds=self.jointOperationIds,
        )
        event.retrieved_at=self.retrieved_at-other.retrieved_at
        return event
    
    @staticmethod
    def average(events_list: List['Event']) -> 'Event':
        count = len(events_list)
        if count == 0:
            return Event()
        
        avg_health = sum(event.health for event in events_list if event.health is not None) // count
        avg_time=  sum(event.retrieved_at.total_seconds() for event in events_list if event.retrieved_at is not None) // count
        avg_event = Event(
            health=avg_health,
            maxHealth=events_list[0].maxHealth,
            faction=events_list[0].faction,
            startTime=events_list[0].startTime,
            endTime=events_list[0].endTime,
            eventType=events_list[0].eventType,
            id=events_list[0].id,
            campaignId=events_list[0].campaignId,
            jointOperationIds=events_list[0].jointOperationIds,
        )
        avg_event.retrieved_at=datetime.timedelta(seconds=avg_time)
        return avg_event
    
    def estimate_remaining_lib_time(self, diff:'Event'):
        time_elapsed=diff.retrieved_at
        if time_elapsed.total_seconds()==0:
            return f""
        change=diff.health/time_elapsed.total_seconds()
        if change==0:
            return f"Stalemate."
        if change>0:
            return f"Losing"
        estimated_seconds=abs(self.health/change)
        timeval= self.retrieved_at+datetime.timedelta(seconds=estimated_seconds)
        return f"{round(change,5)},{fdt(timeval,'R')}"
        pass

