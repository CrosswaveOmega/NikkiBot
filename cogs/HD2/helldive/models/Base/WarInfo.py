from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel

from .HomeWorld import HomeWorld
from .PlanetInfo import PlanetInfo


class WarInfo(BaseApiModel):
    """
    None model
        Represents mostly static information of the current galactic war.

    """

    warId: Optional[int] = Field(alias="warId", default=None)

    startDate: Optional[int] = Field(alias="startDate", default=None)

    endDate: Optional[int] = Field(alias="endDate", default=None)

    minimumClientVersion: Optional[str] = Field(
        alias="minimumClientVersion", default=None
    )

    planetInfos: Optional[List[Optional[PlanetInfo]]] = Field(
        alias="planetInfos", default=[]
    )

    homeWorlds: Optional[List[Optional[HomeWorld]]] = Field(
        alias="homeWorlds", default=[]
    )

    capitalInfos: Optional[List[Any]] = Field(alias="capitalInfos", default=[])

    planetPermanentEffects: Optional[List[Any]] = Field(
        alias="planetPermanentEffects", default=[]
    )
