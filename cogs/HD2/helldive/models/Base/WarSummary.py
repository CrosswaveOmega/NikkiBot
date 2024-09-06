from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel

from .GalaxyStats import GalaxyStats
from .PlanetStats import PlanetStats


class WarSummary(BaseApiModel):
    """
    None model
        Gets general statistics about the galaxy and specific planets.

    """

    galaxy_stats: Optional[GalaxyStats] = Field(alias="galaxy_stats", default=None)

    planets_stats: Optional[List[Optional[PlanetStats]]] = Field(
        alias="planets_stats", default=None
    )
