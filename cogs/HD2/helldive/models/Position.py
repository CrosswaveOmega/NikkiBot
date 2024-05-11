from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class Position(BaseApiModel):
    """
    None model
        Represents a position on the galactic war map.

    """

    x: Optional[float] = Field(alias="x", default=None)

    y: Optional[float] = Field(alias="y", default=None)
