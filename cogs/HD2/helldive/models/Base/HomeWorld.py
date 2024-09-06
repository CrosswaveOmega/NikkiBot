from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class HomeWorld(BaseApiModel):
    """
    None model
        Represents information about the homeworld(s) of a given race.

    """

    race: Optional[int] = Field(alias="race", default=None)

    planetIndices: Optional[List[int]] = Field(alias="planetIndices", default=None)
