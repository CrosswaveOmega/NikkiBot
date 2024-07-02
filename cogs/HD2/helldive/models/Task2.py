from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel
import json
from .Planet import Planet

task_types = {3: "Eradicate", 11: "Liberation", 12: "Defense", 13: "Control"}

value_types = {
    1: "race",
    2: "unknown",
    3: "goal",
    4: "unknown1",
    5: "unknown2",
    6: "unknown3",
    7: "unknown4",
    8: "unknown5",
    9: "unknown6",
    10: "unknown7",
    11: "liberate",
    12: "planet_index",
}
faction_names = {
    0: "Anything",
    1: "Humans",
    2: "Terminids",
    3: "Automaton",
    4: "Illuminate",
    5: "ERR",
    15: "ERR",
}


from utility import changeformatif as cfi
from utility import extract_timestamp as et
from utility import human_format as hf
from utility import select_emoji as emj


class Task2(BaseApiModel):
    """
        None model
            Represents a task in an Assignment that needs to be completed
    to finish the assignment.

    """

    type: Optional[int] = Field(alias="type", default=None)

    values: Optional[List[int]] = Field(alias="values", default=None)

    valueTypes: Optional[List[int]] = Field(alias="valueTypes", default=None)

    def taskAdvanced(self):
        '''return task type, and dictionary containing task details.'''
        task_type = task_types.get(self["type"], "Unknown Task Type")
        taskdata = {"planet_index": "ERR", "race": 15}

        for v, vt in zip(self["values"], self["valueTypes"]):
            # print(v, value_types.get(vt, "Unmapped vt"))
            taskdata[value_types[vt]] = v

        return task_type, taskdata

    def task_str(
        self,
        curr_progress,
        task_type: str,
        taskdata: Dict[str, Any],
        e=0,
        planets: Dict[int, Planet] = {},
        show_faction=False,
    ):
        curr = curr_progress
        taskstr = f"{e}. {task_type}: {hf(curr)}"
        if self["type"] in (11, 13):
            planet_id = taskdata["planet_index"]
            planet_name = "ERR"
            health = "?"
            mode = ""
            if int(planet_id) in planets:
                planet = planets[int(planet_id)]
                planet_name = planet.get_name()
                health = planet.health_percent()
            if self["type"] == 11:
                mode = "Liberate"
                taskstr = f"{e}. Liberate {planet_name}. Status: `{'ok' if curr==1 else f'{health},{curr}'}`"
            if self["type"] == 13:
                mode = "Control"
                taskstr = f"{e}. Control {planet_name}. Status:`{'ok' if curr==1 else f'{health},{curr}'}`"

        elif self["type"] == 12:
            planet_name = taskdata["planet_index"]
            if self.values:
                taskstr += f"{self.values[0]} planets"
            else:
                taskstr += "Defend planets?"
        elif self["type"] == 3:
            faction_name = faction_names.get(
                taskdata["race"], f"Unknown Faction {taskdata['race']}"
            )
            taskstr += f"/{hf(taskdata['goal'])} ({(int(curr)/int(taskdata['goal']))*100.0}){faction_name}"
        else:
            taskstr += f"DATA CORRUPTED.{json.dumps(self)[:50]}."
        return taskstr
