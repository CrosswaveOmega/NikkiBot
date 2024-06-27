from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class Reward(BaseApiModel):
    """
    None model
        Represents the reward of an Assignment.

    """

    type: Optional[int] = Field(alias="type", default=None)

    id32: Optional[int] = Field(alias="id32", default=None)

    amount: Optional[int] = Field(alias="amount", default=None)
