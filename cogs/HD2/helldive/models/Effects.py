from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class PlanetActiveEffects(BaseApiModel):
    """
    None model
        Active Planet Effects, with the index and galacticEffectId

    """

    index: Optional[int] = Field(alias="index", default=None)

    galacticEffectId: Optional[int] = Field(alias="galacticEffectId", default=None)


class KnownPlanetEffect(BaseApiModel):
    """
    None model
        All known planet effects, with a name and description.
    """

    galacticEffectId: Optional[int] = Field(alias="galacticEffectId", default=None)

    name: Optional[str] = Field(alias="name", default=None)

    description: Optional[str] = Field(alias="description", default=None)
