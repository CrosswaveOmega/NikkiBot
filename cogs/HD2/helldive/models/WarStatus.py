from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .Campaign import Campaign
from .JointOperation import JointOperation
from .PlanetAttack import PlanetAttack
from .PlanetEvent import PlanetEvent
from .PlanetStatus import PlanetStatus
from .GlobalEvent import GlobalEvent


class PlanetActiveEffects(BaseApiModel):
    """
    None model
        Represents a snapshot of the current status of the galactic war.

    """

    index: Optional[int] = Field(alias="index", default=None)

    galacticEffectId: Optional[int] = Field(alias="galacticEffectId", default=None)


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
        alias="planetStatus", default=None
    )

    planetAttacks: Optional[List[Optional[PlanetAttack]]] = Field(
        alias="planetAttacks", default=None
    )

    campaigns: Optional[List[Optional[Campaign]]] = Field(
        alias="campaigns", default=None
    )

    jointOperations: Optional[List[Optional[JointOperation]]] = Field(
        alias="jointOperations", default=None
    )

    planetEvents: Optional[List[Optional[PlanetEvent]]] = Field(
        alias="planetEvents", default=None
    )

    communityTargets: Optional[List[Any]] = Field(
        alias="communityTargets", default=None
    )

    planetActiveEffects: Optional[List[PlanetActiveEffects]] = Field(
        alias="planetActiveEffects", default=None
    )

    globalEvents: Optional[List[GlobalEvent]] = Field(
        alias="globalEvents", default=None
    )

    superEarthWarResults: Optional[List[Any]] = Field(
        alias="superEarthWarResults", default=None
    )
