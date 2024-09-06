from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class PlanetStatus(BaseApiModel):
    """
    None model
        Represents the &#39;current&#39; status of a planet in the galactic war.

    """

    index: Optional[int] = Field(alias="index", default=None)

    owner: Optional[int] = Field(alias="owner", default=None)

    health: Optional[int] = Field(alias="health", default=None)

    regenPerSecond: Optional[float] = Field(alias="regenPerSecond", default=None)

    players: Optional[int] = Field(alias="players", default=None)

    def __str__(self):
        return f"{self.index}-{self.owner}-{self.regenPerSecond}"

    def __repr__(self):
        return f"{self.index}-{self.owner}-{self.regenPerSecond}"
