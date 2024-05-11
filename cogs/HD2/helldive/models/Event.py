from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


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
        return Event(
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
