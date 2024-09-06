from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class Campaign(BaseApiModel):
    """
    None model
        Contains information of ongoing campaigns.

    """

    id: Optional[int] = Field(alias="id", default=None)

    planetIndex: Optional[int] = Field(alias="planetIndex", default=None)

    type: Optional[int] = Field(alias="type", default=None)

    count: Optional[int] = Field(alias="count", default=None)
