from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel
import json
from .Planet import Planet

task_types = {
    2: "Get samples",
    3: "Eradicate",
    4: "Objectives",
    7: "Extract",
    11: "Liberation",
    12: "Defense",
    13: "Control",
}

value_types = {
    1: "race",
    2: "unknown",
    3: "goal",
    4: "unknown1",
    5: "rarity",
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
samples={
    3992382197:'Common',
    2985106497:'Rare',
}

from .ABC.utils import changeformatif as cfi
from .ABC.utils import extract_timestamp as et
from .ABC.utils import human_format as hf
from .ABC.utils import select_emoji as emj


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
        """return task type, and dictionary containing task details."""
        task_type = task_types.get(self["type"], f"Unknown Task Type {self['type']}")
        taskdata = {}

        for v, vt in zip(self["values"], self["valueTypes"]):
            # print(v, value_types.get(vt, "Unmapped vt"))

            if value_types[vt] in taskdata:
                taskdata[value_types[vt]].append(v)
            else:
                taskdata[value_types[vt]] = [v]

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
            if not all(key in taskdata for key in ["planet_index"]):
                dump = json.dumps(taskdata, default=str)[:108]
                taskstr += f"{dump}"
                return
            planet_id = taskdata["planet_index"][0]
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
        elif self['type']==2:
            dump = json.dumps(taskdata, default=str)[:258]
            taskstr += f"{dump}"
        elif self["type"] == 12:
            planet_name = taskdata["planet_index"]
            if self.values:
                taskstr += json.dumps(taskdata, default=str)[:258]
            else:
                taskstr += "Defend planets?"
        elif self["type"] == 3:
            if not all(key in taskdata for key in ["goal", "race"]):
                dump = json.dumps(taskdata, default=str)[:258]
                taskstr += f"{dump}"
                return
            faction_name = faction_names.get(
                taskdata["race"][0], f"Unknown Faction {taskdata['race'][0]}"
            )
            goal = taskdata["goal"][0]

            taskstr += f"/{hf(goal)} ({(int(curr)/int(goal))*100.0}) {faction_name}"
            lc = taskdata.get("liberate", None)
            onplanet = taskdata.get("planet_index", None)
            if onplanet is not None and lc is not None:
                if lc[0]:
                    for ind in onplanet:
                        if int(ind) in planets:
                            planet = planets[int(ind)]
                            planet_name = planet.get_name()
                            taskstr += f", On {planet_name}"
        else:
            dump = json.dumps(taskdata, default=str)[:258]
            taskstr += f"{dump}"
        return taskstr
