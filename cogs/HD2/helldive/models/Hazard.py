from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class Hazard(BaseApiModel):
    """
    None model
        Describes an environmental hazard that can be present on a Planet.

    """

    name: Optional[str] = Field(alias="name", default=None)

    description: Optional[str] = Field(alias="description", default=None)
