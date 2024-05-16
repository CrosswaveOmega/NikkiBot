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
        event.retrieved_at=other.retrieved_at
        return event
    
    def estimate_remaining_lib_time(self, diff:'Event'):
        time_elapsed=self.retrieved_at-diff.retrieved_at
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

