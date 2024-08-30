from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .Reward2 import Reward2
from .Task2 import Task2
from .Planet import Planet
from .Reward import Reward
from PIL import Image, ImageDraw, ImageFont
from discord.utils import format_dt as fdt
from .ABC.utils import changeformatif as cfi
from .ABC.utils import extract_timestamp as et
from .ABC.utils import human_format as hf
from .ABC.utils import select_emoji as emj


class Assignment2(BaseApiModel):
    """
        None model
            Represents an assignment given by Super Earth to the community.
    This is also known as &#39;Major Order&#39;s in the game.

    """

    id: Optional[int] = Field(alias="id", default=None)

    progress: Optional[List[int]] = Field(alias="progress", default=None)

    title: Optional[Union[str, Dict[str, Any]]] = Field(alias="title", default=None)

    briefing: Optional[Union[str, Dict[str, Any]]] = Field(
        alias="briefing", default=None
    )

    description: Optional[Union[str, Dict[str, Any]]] = Field(
        alias="description", default=None
    )

    tasks: Optional[List[Optional[Task2]]] = Field(alias="tasks", default=None)

    reward: Optional[Reward2] = Field(alias="reward", default=None)

    rewards: Optional[List[Optional[Reward]]] = Field(alias="rewards", default=None)

    expiration: Optional[str] = Field(alias="expiration", default=None)

    def __sub__(self, other:'Assignment2'):
        new_progress = [s - o for s, o in zip(self.progress, other.progress)]
        return Assignment2(
            id=self.id,
            progress=new_progress,
            title=self.title,
            briefing=self.briefing,
            description=self.description,
            tasks=self.tasks,
            reward=self.reward,
            rewards=self.rewards,
            expiration=self.expiration,
            retrieved_at=self.retrieved_at-other.retrieved_at
        )

    def get_task_planets(self) -> List[int]:
        planets = []
        for e, task in enumerate(self.tasks):
            task_type, taskdata = task.taskAdvanced()
            if "planet_index" in taskdata:
                planets.append(taskdata["planet_index"])
        return planets

    def to_str(self) -> str:
        planets = {}
        progress = self.progress
        tasks = ""
        exptime = fdt(et(self.expiration), "f")
        for e, task in enumerate(self.tasks):
            task_type, taskdata = task.taskAdvanced()
            tasks += task.task_str(progress[e], task_type, taskdata, e, planets) + "\n"
        tex = f"{self.briefing},by {exptime}\n{tasks}"

        return tex
