from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class PlanetActiveEffects(BaseApiModel):
    """
    None model
        Active Planet Effects, with the index and galacticEffectId

    """

    index: Optional[int] = Field(alias="index", default=None)

    galacticEffectId: Optional[int] = Field(alias="galacticEffectId", default=None)
