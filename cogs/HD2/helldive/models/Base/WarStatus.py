import json
from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel

from .Campaign import Campaign
from .JointOperation import JointOperation
from .PlanetAttack import PlanetAttack
from .PlanetEvent import PlanetEvent
from .PlanetStatus import PlanetStatus
from .GlobalEvent import GlobalEvent
from ..Position import Position
from .Effects import PlanetActiveEffects


class WarStatus(BaseApiModel):
    """
    None model
        Represents a snapshot of the current status of the galactic war.

    """

    warId: Optional[int] = Field(alias="warId", default=None)

    time: Optional[int] = Field(alias="time", default=None)

    impactMultiplier: Optional[float] = Field(alias="impactMultiplier", default=None)

    storyBeatId32: Optional[int] = Field(alias="storyBeatId32", default=None)

    planetStatus: Optional[List[Optional[PlanetStatus]]] = Field(
        alias="planetStatus", default=[]
    )

    planetAttacks: Optional[List[Optional[PlanetAttack]]] = Field(
        alias="planetAttacks", default=[]
    )

    campaigns: Optional[List[Optional[Campaign]]] = Field(alias="campaigns", default=[])

    jointOperations: Optional[List[Optional[JointOperation]]] = Field(
        alias="jointOperations", default=[]
    )

    planetEvents: Optional[List[Optional[PlanetEvent]]] = Field(
        alias="planetEvents", default=[]
    )

    communityTargets: Optional[List[Any]] = Field(alias="communityTargets", default=[])
    activeElectionPolicyEffects: Optional[List[Any]] = Field(
        alias="activeElectionPolicyEffects", default=[]
    )
    planetActiveEffects: Optional[List[PlanetActiveEffects]] = Field(
        alias="planetActiveEffects", default=[]
    )

    globalEvents: Optional[List[GlobalEvent]] = Field(alias="globalEvents", default=[])

    superEarthWarResults: Optional[List[Any]] = Field(
        alias="superEarthWarResults", default=[]
    )

    layoutVersion: Optional[int] = Field(alias="layoutVersion", default=None)
