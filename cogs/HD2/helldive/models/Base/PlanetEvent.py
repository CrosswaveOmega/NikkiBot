from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


from ..ABC.utils import (
    human_format as hf,
    select_emoji as emj,
    changeformatif as cfi,
    extract_timestamp as et,
)


class PlanetEvent(BaseApiModel):
    """
    None model
        An ongoing event on a planet.

    """

    id: Optional[int] = Field(alias="id", default=None)

    planetIndex: Optional[int] = Field(alias="planetIndex", default=None)

    eventType: Optional[int] = Field(alias="eventType", default=None)

    race: Optional[int] = Field(alias="race", default=None)

    health: Optional[int] = Field(alias="health", default=None)

    maxHealth: Optional[int] = Field(alias="maxHealth", default=None)

    startTime: Optional[int] = Field(alias="startTime", default=None)

    expireTime: Optional[int] = Field(alias="expireTime", default=None)

    campaignId: Optional[int] = Field(alias="campaignId", default=None)

    jointOperationIds: Optional[List[int]] = Field(
        alias="jointOperationIds", default=None
    )

    def long_event_details(self):
        factions = {1: "Humans", 2: "Terminids", 3: "Automaton", 4: "Illuminate"}
        event_details = (
            f"ID: {self.id}, Type: {self.eventType}, Faction: {factions.get(self.race,'UNKNOWN')}\n"
            f"Event Health: `{(self.health)}/{(self.maxHealth)}`\n"
            f"Start Time: {self.startTime}, End Time: {self.expireTime}\n"
            f"Campaign ID: C{self.campaignId}, Joint Operation IDs: {', '.join(map(str, self.jointOperationIds))}"
        )
        return event_details
