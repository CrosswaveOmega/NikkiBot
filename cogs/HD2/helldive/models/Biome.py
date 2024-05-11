from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class Biome(BaseApiModel):
    """
    None model
        Represents information about a biome of a planet.

    """

    name: Optional[str] = Field(alias="name", default=None)

    description: Optional[str] = Field(alias="description", default=None)
