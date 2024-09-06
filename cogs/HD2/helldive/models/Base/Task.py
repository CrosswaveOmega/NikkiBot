from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class Task(BaseApiModel):
    """
        None model
            Represents a task in an Assignment.
    It&#39;s exact values are not known, therefore little of it&#39;s purpose is clear.

    """

    type: Optional[int] = Field(alias="type", default=None)

    values: Optional[List[int]] = Field(alias="values", default=None)

    valueTypes: Optional[List[int]] = Field(alias="valueTypes", default=None)
