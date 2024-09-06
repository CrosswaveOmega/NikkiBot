from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class PlanetStats(BaseApiModel):
    """
    None model
        Similar to GalaxyStats, but scoped to a specific planet.

    """

    planetIndex: Optional[int] = Field(alias="planetIndex", default=0)

    missionsWon: Optional[int] = Field(alias="missionsWon", default=0)

    missionsLost: Optional[int] = Field(alias="missionsLost", default=0)

    missionTime: Optional[int] = Field(alias="missionTime", default=0)

    bugKills: Optional[int] = Field(alias="bugKills", default=0)

    automatonKills: Optional[int] = Field(alias="automatonKills", default=0)

    illuminateKills: Optional[int] = Field(alias="illuminateKills", default=0)

    bulletsFired: Optional[int] = Field(alias="bulletsFired", default=0)

    bulletsHit: Optional[int] = Field(alias="bulletsHit", default=0)

    timePlayed: Optional[int] = Field(alias="timePlayed", default=0)

    deaths: Optional[int] = Field(alias="deaths", default=0)

    revives: Optional[int] = Field(alias="revives", default=0)

    friendlies: Optional[int] = Field(alias="friendlies", default=0)

    missionSuccessRate: Optional[int] = Field(alias="missionSuccessRate", default=0)

    accurracy: Optional[int] = Field(alias="accurracy", default=0)
