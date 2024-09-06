from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel

from .Reward import Reward
from .Task import Task


class Setting(BaseApiModel):
    """
    None model
        Contains the details of an Assignment like reward and requirements.

    """

    type: Optional[int] = Field(alias="type", default=None)

    overrideTitle: Optional[str] = Field(alias="overrideTitle", default=None)

    overrideBrief: Optional[str] = Field(alias="overrideBrief", default=None)

    taskDescription: Optional[str] = Field(alias="taskDescription", default=None)

    tasks: Optional[List[Optional[Task]]] = Field(alias="tasks", default=None)

    reward: Optional[Reward] = Field(alias="reward", default=None)

    rewards: Optional[List[Optional[Reward]]] = Field(alias="rewards", default=None)

    flags: Optional[int] = Field(alias="flags", default=None)
