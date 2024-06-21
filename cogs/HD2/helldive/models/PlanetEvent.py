from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class PlanetEvent(BaseApiModel):
    """
    None model
        An ongoing event on a planet.

    """

    id: Optional[int] = Field(alias="id", default=None)

    planetIndex: Optional[int] = Field(alias="planetIndex", default=None)

    eventType: Optional[int] = Field(alias="eventType", default=None)

    race: Optional[int] = Field(alias="race", default=None)

    health: Optional[int] = Field(alias="health", default=None)

    maxHealth: Optional[int] = Field(alias="maxHealth", default=None)

    startTime: Optional[int] = Field(alias="startTime", default=None)

    expireTime: Optional[int] = Field(alias="expireTime", default=None)

    campaignId: Optional[int] = Field(alias="campaignId", default=None)

    jointOperationIds: Optional[List[int]] = Field(
        alias="jointOperationIds", default=None
    )
