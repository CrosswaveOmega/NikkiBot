from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class PlanetAttack(BaseApiModel):
    """
    None model
        Represents an attack on a PlanetInfo.

    """

    source: Optional[int] = Field(alias="source", default=None)

    target: Optional[int] = Field(alias="target", default=None)
