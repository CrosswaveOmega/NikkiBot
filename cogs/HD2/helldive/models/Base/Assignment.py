from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel

from .Setting import Setting


class Assignment(BaseApiModel):
    """
    None model
        Represents an assignment given from Super Earth to the Helldivers.

    """

    id32: Optional[int] = Field(alias="id32", default=None)

    progress: Optional[List[int]] = Field(alias="progress", default=None)

    expiresIn: Optional[int] = Field(alias="expiresIn", default=None)

    setting: Optional[Setting] = Field(alias="setting", default=None)
