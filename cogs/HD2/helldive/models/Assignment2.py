from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .Reward2 import Reward2
from .Task2 import Task2


class Assignment2(BaseApiModel):
    """
        None model
            Represents an assignment given by Super Earth to the community.
    This is also known as &#39;Major Order&#39;s in the game.

    """

    id: Optional[int] = Field(alias="id", default=None)

    progress: Optional[List[int]] = Field(alias="progress", default=None)

    title: Optional[Union[str, Dict[str, Any]]] = Field(alias="title", default=None)

    briefing: Optional[Union[str, Dict[str, Any]]] = Field(alias="briefing", default=None)

    description: Optional[Union[str, Dict[str, Any]]] = Field(alias="description", default=None)

    tasks: Optional[List[Optional[Task2]]] = Field(alias="tasks", default=None)

    reward: Optional[Reward2] = Field(alias="reward", default=None)

    expiration: Optional[str] = Field(alias="expiration", default=None)

    
    def __sub__(self, other):
        new_progress = [s - o for s, o in zip(self.progress, other.progress)]
        return Assignment2(
            id=self.id,
            progress=new_progress,
            title=self.title,
            briefing=self.briefing,
            description=self.description,
            tasks=self.tasks,
            reward=self.reward,
            expiration=self.expiration
        )