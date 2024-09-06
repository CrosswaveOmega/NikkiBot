from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class JointOperation(BaseApiModel):
    """
    None model
        Represents a joint operation.

    """

    id: Optional[int] = Field(alias="id", default=None)

    planetIndex: Optional[int] = Field(alias="planetIndex", default=None)

    hqNodeIndex: Optional[int] = Field(alias="hqNodeIndex", default=None)
