from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel
import json
from .Planet import Planet

from .ABC.utils import changeformatif as cfi
from .ABC.utils import extract_timestamp as et
from .ABC.utils import human_format as hf
from .ABC.utils import select_emoji as emj

from ..constants import task_types, value_types, faction_names, samples, enemies


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
        last_progess=None,
        projected=None,
        show_faction=False,
    ):
        curr = curr_progress
        taskstr = f"{e}. {task_type}: {hf(curr)}"
        if True:
            if self["type"] in (11, 13):
                if not all(key in taskdata for key in ["planet"]):
                    dump = json.dumps(taskdata, default=str)[:108]
                    taskstr += f"{dump}"
                    return taskstr
                planet_id = taskdata["planet"][0]
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
            elif self["type"] == 2:
                if not all(key in taskdata for key in ["goal"]):
                    dump = json.dumps(taskdata, default=str)[:258]
                    taskstr += f"{dump}"
                    return taskstr
                faction_name = ""
                if "faction" in taskdata:
                    faction_name = (
                        "("
                        + faction_names.get(
                            taskdata["faction"][0],
                            f"Unknown Faction {taskdata['faction'][0]}",
                        )
                        + " type)"
                    )
                goal = taskdata["goal"][0]
                rarity = ""
                lc = taskdata.get("hasPlanet", None)
                onplanet = taskdata.get("planet", None)

                if "itemId" in taskdata:
                    rare = taskdata["itemId"][0]
                    rarity = samples.get(rare, rare) + " "

                taskstr += f"/{hf(goal)} {rarity}samples ({round((int(curr)/int(goal))*100.0,3)}) {faction_name}"

                if onplanet is not None and lc is not None:
                    if lc[0]:
                        for ind in onplanet:
                            if int(ind) in planets:
                                planet = planets[int(ind)]
                                planet_name = planet.get_name()
                                taskstr += f", On {planet_name}"
            elif self["type"] == 12:
                if not all(key in taskdata for key in ["goal"]):
                    dump = json.dumps(taskdata, default=str)[:258]
                    taskstr += f"{dump}"
                    return taskstr
                faction_name = ""
                if "faction" in taskdata:
                    faction_name = (
                        " from "
                        + faction_names.get(
                            taskdata["faction"][0],
                            f"Unknown Faction {taskdata['faction'][0]}",
                        )
                        + ""
                    )
                goal = taskdata["goal"][0]
                planet_name = taskdata["planet"]
                taskstr = f"{e}. Defend {hf(curr)}/{hf(goal)} planets{faction_name}"
                lc = taskdata.get("hasPlanet", None)
                onplanet = taskdata.get("planet", None)
                if onplanet is not None and lc is not None:
                    if lc[0]:
                        for ind in onplanet:
                            if int(ind) in planets:
                                planet = planets[int(ind)]
                                planet_name = planet.get_name()
                                taskstr += f", On {planet_name}"
            elif self["type"] == 3:
                ##Exterminate.
                if not all(key in taskdata for key in ["goal", "faction"]):
                    dump = json.dumps(taskdata, default=str)[:258]
                    taskstr += f"{dump}"
                    return taskstr
                faction_name = faction_names.get(
                    taskdata["faction"][0], f"Unknown Faction {taskdata['faction'][0]}"
                )
                goal = taskdata["goal"][0]
                enemy_id = taskdata.get("enemyID", None)
                enemy = ""
                if enemy_id is not None:
                    eid = enemy_id[0]
                    if eid:
                        enemy = enemies.get(eid, f"UNKNOWN {eid}")

                taskstr += f"/{hf(goal)} ({(int(curr)/int(goal))*100.0}) {enemy} {faction_name}"
                
                lc = taskdata.get("hasPlanet", None)
                onplanet = taskdata.get("planet", None)
                if onplanet is not None and lc is not None:
                    if lc[0]:
                        for ind in onplanet:
                            if int(ind) in planets:
                                planet = planets[int(ind)]
                                planet_name = planet.get_name()
                                taskstr += f", On {planet_name}"
                if projected:
                    status="UNKNOWN"
                    if curr>goal:
                        status="VICTORY!"
                    elif projected>goal:
                        status="ABOVE QUOTA!"
                    elif projected<goal:
                        status="WARNING, UNDER QUOTA!"
                    taskstr+=f"\n  * Projected Result:`{projected}`, **{status}**  "
            else:
                dump = json.dumps(taskdata, default=str)[:258]
                taskstr += f"{dump}"
        if last_progess:
            taskstr+=f"`[change {last_progess}]`"
        return taskstr
