import datetime
from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel, HealthMixin

from .Biome import Biome
from .Event import Event
from .Hazard import Hazard
from .Position import Position
from .Statistics import Statistics
from .PlanetStatus import PlanetStatus
from .PlanetInfo import PlanetInfo
from .Planet import Planet
from .PlanetStats import PlanetStats


from ..constants import task_types, value_types, faction_names, samples

from .ABC.utils import (
    human_format as hf,
    select_emoji as emj,
    changeformatif as cfi,
    extract_timestamp as et,
)
from discord.utils import format_dt as fdt


class PlanetStatic(BaseApiModel):
    name: Optional[str] = Field(alias="name", default=None)
    sector: Optional[str] = Field(alias="sector", default=None)
    biome: Optional[str] = Field(alias="biome", default=None)
    environmentals: Optional[List[str]] = Field(alias="environmentals", default=None)
    names: Optional[Dict[str, str]] = Field(alias="names", default=None)


class GalaxyStatic(BaseApiModel):
    """
    Pydantic reprersentation of all the json files pertaining to planets.
    """

    biomes: Optional[Dict[str, Biome]] = Field(alias="biomes", default=None)

    environmentals: Optional[Dict[str, Hazard]] = Field(
        alias="environmentals", default=None
    )

    planets: Optional[Dict[int, PlanetStatic]] = Field(alias="planets", default=None)

    def build_planet(
        self,
        index: int,
        planetStatus: PlanetStatus,
        planetInfo: PlanetInfo,
        stats: PlanetStats,
    ) -> Planet:
        planet_base = self.planets.get(index, None)
        if not planet_base:
            return None
        biome = self.biomes.get(planet_base.biome, None)
        env = [self.environmentals.get(e, None) for e in planet_base.environmentals]
        stats = Statistics(
            playerCount=planetStatus.players,
            missionsWon=stats.missionsWon,
            missionsLost=stats.missionsLost,
            missionTime=stats.missionTime,
            terminidKills=stats.bugKills,
            automatonKills=stats.automatonKills,
            illuminateKills=stats.illuminateKills,
            bulletsFired=stats.bulletsFired,
            bulletsHit=stats.bulletsHit,
            timePlayed=stats.timePlayed,
            deaths=stats.deaths,
            revives=stats.revives,
            friendlies=stats.friendlies,
            missionSuccessRate=stats.missionSuccessRate,
            accuracy=stats.accurracy,
        )
        pos = planetInfo.position
        planet = Planet(
            index=index,
            name=planet_base.name,
            sector=planet_base.sector,
            biome=biome,
            hazards=env,
            position=Position(x=pos.x, y=pos.y),
            waypoints=planetInfo.waypoints,
            maxHealth=planetInfo.maxHealth,
            health=planetStatus.health,
            disabled=planetInfo.disabled,
            initialOwner=faction_names.get(planetInfo.initialOwner, "???"),
            currentOwner=faction_names.get(planetStatus.owner, "???"),
            regenPerSecond=planetStatus.regenPerSecond,
            statistics=stats,
        )
        return planet
