from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class Reward2(BaseApiModel):
    """
    None model
        The reward for completing an Assignment.

    """

    type: Optional[int] = Field(alias="type", default=None)

    amount: Optional[int] = Field(alias="amount", default=None)
