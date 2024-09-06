from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class WarId(BaseApiModel):
    """
    None model
        Represents the ID returned from the WarID endpoint.

    """

    id: Optional[int] = Field(alias="id", default=None)
