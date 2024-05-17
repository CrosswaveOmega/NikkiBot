from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .Planet import Planet


class Campaign2(BaseApiModel):
    """
    None model
        Represents an ongoing campaign on a planet.

    """

    id: Optional[int] = Field(alias="id", default=None)

    planet: Optional[Planet] = Field(alias="planet", default=None)

    type: Optional[int] = Field(alias="type", default=None)

    count: Optional[int] = Field(alias="count", default=None)

    def __sub__(self, other:'Campaign2')->'Campaign2':
        camp=Campaign2(
            id=self.id,
            planet=self.planet-other.planet,
            type=self.type,
            count=self.count
        )
        camp.retrieved_at=self.retrieved_at-other.retrieved_at
        return camp
