from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .Reward2 import Reward2
from .Task2 import Task2
from .Planet import Planet
from PIL import Image,ImageDraw,ImageFont
from discord.utils import format_dt as fdt
from utility import changeformatif as cfi
from utility import extract_timestamp as et
from utility import human_format as hf
from utility import select_emoji as emj, wrap_text

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
            expiration=self.expiration,
        )

    def get_task_planets(self) -> List[int]:
        planets = []
        for e, task in enumerate(self.tasks):
            task_type, taskdata = task.taskAdvanced()
            if "planet_index" in taskdata:
                planets.append(taskdata["planet_index"])
        return planets
    
    def get_overview_image(self, planets: Dict[int, Planet] = None):
        if not planets: planets={}
        width, height = 800, 1000  # Increased height to accommodate more text
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        
        # Load a font
        font = ImageFont.truetype("arial.ttf", size=20)
        
        # Extract self
        did = self["id"]
        title = self["title"]
        briefing = self["briefing"]
        progress = self["progress"]

        # Add title and author
        text = f"Assignment A#{did}"
        wrapped_text = wrap_text(draw, text, font, width - 20)
        y_text = 10
        for line in wrapped_text:
            draw.text((10, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

        text = f"Title: {title}"
        wrapped_text = wrap_text(draw, text, font, width - 20)
        for line in wrapped_text:
            draw.text((10, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

        text = f"Briefing: {briefing}"
        wrapped_text = wrap_text(draw, text, font, width - 20)
        for line in wrapped_text:
            draw.text((10, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

        # Add objective
        text = "Objective:"
        wrapped_text = wrap_text(draw, text, font, width - 20)
        for line in wrapped_text:
            draw.text((10, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

        text = self["description"]
        wrapped_text = wrap_text(draw, text, font, width - 20)
        for line in wrapped_text:
            draw.text((10, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

        # Add tasks
        tasks = []
        for e, task in enumerate(self.tasks):
            task_type, taskdata = task.taskAdvanced()
            taskstr=task.task_str(progress[e], task_type, taskdata, e, planets)
            print(taskstr)
            tasks.append(taskstr)

        text = "Tasks:"
        wrapped_text = wrap_text(draw, text, font, width - 20)
        for line in wrapped_text:
            draw.text((10, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

        for t in tasks:
            text = t
            wrapped_text = wrap_text(draw, text, font, width - 20)
            for line in wrapped_text:
                draw.text((10, y_text), line, font=font, fill="black")
                y_text += font.getsize(line)[1]

        # Add reward
        text = "Reward:"
        wrapped_text = wrap_text(draw, text, font, width - 20)
        for line in wrapped_text:
            draw.text((10, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

        text = self["reward"].format()
        wrapped_text = wrap_text(draw, text, font, width - 20)
        for line in wrapped_text:
            draw.text((10, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

        # Add expiration
        exptime = et(self["expiration"])

        text = "Expiration:"
        wrapped_text = wrap_text(draw, text, font, width - 20)
        for line in wrapped_text:
            draw.text((10, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

        text = fdt(exptime, "f")
        wrapped_text = wrap_text(draw, text, font, width - 20)
        for line in wrapped_text:
            draw.text((10, y_text), line, font=font, fill="black")
            y_text += font.getsize(line)[1]

        return image


