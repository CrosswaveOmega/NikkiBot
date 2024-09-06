from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class PlanetCoordinates(BaseApiModel):
    """
    None model
        Represents a set of coordinates returned by ArrowHead&#39;s API.

    """

    x: Optional[float] = Field(alias="x", default=None)

    y: Optional[float] = Field(alias="y", default=None)
