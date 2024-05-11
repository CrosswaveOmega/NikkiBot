from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class Task2(BaseApiModel):
    """
        None model
            Represents a task in an Assignment that needs to be completed
    to finish the assignment.

    """

    type: Optional[int] = Field(alias="type", default=None)

    values: Optional[List[int]] = Field(alias="values", default=None)

    valueTypes: Optional[List[int]] = Field(alias="valueTypes", default=None)
