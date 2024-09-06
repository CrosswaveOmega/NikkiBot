from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel

from .PlanetCoordinates import PlanetCoordinates


class PlanetInfo(BaseApiModel):
    """
    None model
        Represents information of a planet from the &#39;WarInfo&#39; endpoint returned by ArrowHead&#39;s API.

    """

    index: Optional[int] = Field(alias="index", default=None)

    settingsHash: Optional[int] = Field(alias="settingsHash", default=None)

    position: Optional[PlanetCoordinates] = Field(alias="position", default=None)

    waypoints: Optional[List[int]] = Field(alias="waypoints", default=None)

    sector: Optional[int] = Field(alias="sector", default=None)

    maxHealth: Optional[int] = Field(alias="maxHealth", default=None)

    disabled: Optional[bool] = Field(alias="disabled", default=None)

    initialOwner: Optional[int] = Field(alias="initialOwner", default=None)
