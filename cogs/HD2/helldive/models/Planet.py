import datetime
from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel, HealthMixin

from .Biome import Biome
from .Event import Event
from .Hazard import Hazard
from .Position import Position
from .Statistics import Statistics
from .Effects import KnownPlanetEffect
from .ABC.utils import (
    human_format as hf,
    select_emoji as emj,
    changeformatif as cfi,
    extract_timestamp as et,
)
from discord.utils import format_dt as fdt


class Planet(BaseApiModel, HealthMixin):
    """
    None model
        Contains all aggregated information AH has about a planet.

    """

    index: Optional[int] = Field(alias="index", default=None)

    name: Optional[Union[str, Dict[str, Any]]] = Field(alias="name", default=None)

    owner: Optional[int] = Field(alias="owner", default=0)

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

    activePlanetEffects: Optional[List[KnownPlanetEffect]] = Field(
        alias="activePlanetEffects", default=None
    )

    event: Optional[Event] = Field(alias="event", default=None)

    statistics: Optional[Statistics] = Field(alias="statistics", default=None)

    attacking: Optional[List[int]] = Field(alias="attacking", default=None)

    def __sub__(self, other: "Planet") -> "Planet":
        """
        Subtract values from another planet.
        """
        # Calculate the values for health, statistics, and event based on subtraction
        new_health = (
            self.health - other.health
            if self.health is not None and other.health is not None
            else None
        )
        new_statistics = (
            self.statistics - other.statistics
            if self.statistics is not None and other.statistics is not None
            else None
        )
        new_event = (
            self.event - other.event
            if self.event is not None and other.event is not None
            else self.event
        )

        # Create a new instance of the Planet class with calculated values
        planet = Planet(
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
        planet.retrieved_at = self.retrieved_at - other.retrieved_at
        return planet

    def calculate_change(self, diff: "Planet") -> float:
        """
        Calculate the rate of change in health over time.

        Args:
            diff (Planet): A Planet object representing the difference in health and time.

        Returns:
            float: The rate of change in health per second.
        """
        time_elapsed = diff.retrieved_at
        if time_elapsed.total_seconds() == 0:
            return 0.0
        return diff.health / time_elapsed.total_seconds()

    def calculate_timeval(self, change: float, is_positive: bool) -> datetime:
        """
        Calculate the future datetime when the planet's health will reach the maxHealth or zero.

        Args:
            change (float): The rate of change in health per second.
            is_positive (bool): A boolean indicating if the change is positive or negative.

        Returns:
            datetime: The estimated future datetime.
        """
        if is_positive:
            estimated_seconds = abs((self.maxHealth - self.health) / change)
        else:
            estimated_seconds = abs(self.health / change)
        return self.retrieved_at + datetime.timedelta(seconds=estimated_seconds)

    def format_estimated_time_string(self, change: float, esttime: datetime.datetime):
        change_str = f"{round(change, 5)}"
        timeval_str = (
            f"Est.Loss {fdt(esttime,'R')}" if change > 0 else f"{fdt(esttime,'R')}"
        )

        return f"`[{change_str} dps]`, {timeval_str}"

    def estimate_remaining_lib_time(self, diff: "Planet") -> str:
        """
        Estimate the remaining life time of the planet based on the current rate of health change.

        Args:
            diff (Planet): A Planet object representing the difference in health and time.

        Returns:
            str: A string representation of the rate of change and the estimated time of loss or gain.
        """
        time_elapsed = diff.retrieved_at
        if time_elapsed.total_seconds() == 0:
            return ""

        change = self.calculate_change(diff)
        if change == 0:
            if self.currentOwner.lower() != "humans":
                return "Stalemate."
            return ""

        timeval = self.calculate_timeval(change, change > 0)

        return self.format_estimated_time_string(change, timeval)

    def get_name(self, faction=True) -> str:
        """Get the name of the planet, along with occupying faction
        and planet index."""
        if not faction:
            return f"P#{self.index}: {self.name}"
        faction = emj(self.currentOwner.lower())
        return f"{faction}P#{self.index}: {self.name}"

    @staticmethod
    def average(planets_list: List["Planet"]) -> "Planet":
        """Average together a list of planet differences over time."""
        count = len(planets_list)
        if count == 0:
            return Planet()

        avg_health = (
            sum(planet.health for planet in planets_list if planet.health is not None)
            // count
        )
        avg_statistics = Statistics.average(
            [
                planet.statistics
                for planet in planets_list
                if planet.statistics is not None
            ]
        )
        avg_event = Event.average(
            [planet.event for planet in planets_list if planet.event is not None]
        )

        avg_time = (
            sum(
                planet.retrieved_at.total_seconds()
                for planet in planets_list
                if planet.retrieved_at is not None
            )
            // count
        )
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
        avg_planet.retrieved_at = datetime.timedelta(seconds=avg_time)
        return avg_planet

    def campaign_against(self) -> str:
        """Get the emoji of the faction that is occupying or defending this planet."""
        faction = emj(self.currentOwner.lower())
        if self.event:
            evt = self.event
            return emj(self.event.faction.lower())
        return faction

    def simple_planet_view(
        self, prev: Optional["Planet"] = None, avg: Optional["Planet"] = None
    ) -> Tuple[str, str]:
        """Return a string containing the formated state of the planet.

        Args:
            prev (Optional[&#39;Planet&#39;], optional):
            avg (Optional[&#39;Planet&#39;], optional):Average stats for the past X planets

        Returns:
            Tuple[str,str]: _description_
        """
        diff = self - self
        if prev is not None:
            diff = prev

        faction = emj(self.currentOwner.lower())

        name = f"{faction}P#{self.index}: {self.name}"
        players = f"{emj('hdi')}: `{self.statistics.playerCount} {cfi(diff.statistics.playerCount)}`"
        out = f"{players}\nHP `{round((self.health/self.maxHealth)*100.0,5)}% {cfi(round((diff.health/self.maxHealth)*100.0,5))}`"
        out += f"\nDecay:`{round((100*(self.regenPerSecond/self.maxHealth))*60*60,2)}`"
        if avg:
            remaining_time = self.estimate_remaining_lib_time(avg)
            out += "\n" + remaining_time
        if self.event:
            evt = self.event
            timev = fdt(et(evt.endTime), "R")
            event_fact = emj(self.event.faction.lower())
            # , {evt.health}{cfi(diff.event.health)}/{evt.maxHealth}.
            out += f"\n Defend from {event_fact} \n Lib {round((evt.health/evt.maxHealth)*100.0, 5)}% {cfi(round((diff.event.health/evt.maxHealth)*100.0, 5))}"
            out += f"\n Deadline: {timev}"
            if avg:
                if avg.event:
                    out += f"\n {self.event.estimate_remaining_lib_time(avg.event)}"

        return name, out
