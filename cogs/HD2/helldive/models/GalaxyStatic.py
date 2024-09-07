import datetime
from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel, HealthMixin

from .Biome import Biome
from .Event import Event
from .Hazard import Hazard
from .Position import Position
from .Statistics import Statistics
from .Base.PlanetStatus import PlanetStatus
from .Base.PlanetInfo import PlanetInfo
from .Planet import Planet
from .Base.PlanetStats import PlanetStats
from .Effects import KnownPlanetEffect

from ..constants import task_types, value_types, faction_names, samples

from .ABC.utils import (
    human_format as hf,
    select_emoji as emj,
    changeformatif as cfi,
    extract_timestamp as et,
)


class EffectStatic(BaseApiModel):
    """
    Pydantic reprersentation of all the json files pertaining to effects
    """

    planetEffects: Dict[int, KnownPlanetEffect] = Field(
        alias="planetEffects", default_factory=dict
    )

    def check_for_id(self, idv):

        if idv in self.planetEffects:
            return self.planetEffects[idv]
        return KnownPlanetEffect(
            galacticEffectId=idv,
            name=f"Effect {idv}",
            description="Mysterious signature...",
        )


class PlanetStatic(BaseApiModel):
    """All static data reguarding each planet"""

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


class StaticAll(BaseApiModel):
    """All the static models in one package."""

    galaxystatic: Optional[GalaxyStatic] = Field(alias="galaxystatic", default=None)

    effectstatic: Optional[EffectStatic] = Field(alias="effectstatic", default=None)
