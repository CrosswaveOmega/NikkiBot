from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .Biome import Biome
from .Event import Event
from .Hazard import Hazard
from .Position import Position
from .Statistics import Statistics


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
        new_event = self.event - other.event if self.event is not None and other.event is not None else None

        # Create a new instance of the Planet class with calculated values
        return Planet(
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

