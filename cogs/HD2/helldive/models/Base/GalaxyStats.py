from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class GalaxyStats(BaseApiModel):
    """
    None model
        Represents galaxy wide statistics.

    """

    missionsWon: Optional[int] = Field(alias="missionsWon", default=None)

    missionsLost: Optional[int] = Field(alias="missionsLost", default=None)

    missionTime: Optional[int] = Field(alias="missionTime", default=None)

    bugKills: Optional[int] = Field(alias="bugKills", default=None)

    automatonKills: Optional[int] = Field(alias="automatonKills", default=None)

    illuminateKills: Optional[int] = Field(alias="illuminateKills", default=None)

    bulletsFired: Optional[int] = Field(alias="bulletsFired", default=None)

    bulletsHit: Optional[int] = Field(alias="bulletsHit", default=None)

    timePlayed: Optional[int] = Field(alias="timePlayed", default=None)

    deaths: Optional[int] = Field(alias="deaths", default=None)

    revives: Optional[int] = Field(alias="revives", default=None)

    friendlies: Optional[int] = Field(alias="friendlies", default=None)

    missionSuccessRate: Optional[int] = Field(alias="missionSuccessRate", default=None)

    accurracy: Optional[int] = Field(alias="accurracy", default=None)
