import json
from typing import Dict, List, Optional, Tuple

import discord

from .helldive import Assignment2, Campaign2, Planet, War

"""
Collection of embeds for formatting.
"""
from collections import defaultdict

from discord.utils import format_dt as fdt

from utility import changeformatif as cfi
from utility import extract_timestamp as et
from utility import human_format as hf
from utility import select_emoji as emj
import random
from .GameStatus import ApiStatus, get_feature_dictionary
from .predict import make_prediction_for_eps


def create_war_embed(data: War, last=None):
    stats = data["statistics"]
    stat_str = data.statistics.format_statistics()
    if stats and (last is not None):
        stat_str = stats.diff_format(stats - last.statistics)

    embed = discord.Embed(title="War", description=f"{stat_str}", color=0xFF0000)

    embed.add_field(name="Started", value=fdt(et(data["started"]), "F"), inline=False)
    embed.add_field(name="Ended", value=fdt(et(data["ended"]), "F"), inline=False)
    embed.add_field(name="Now", value=fdt(et(data["now"]), "F"), inline=False)
    embed.add_field(name="Client Version", value=data["clientVersion"], inline=False)

    factions = ", ".join(data["factions"])
    embed.add_field(name="Factions", value=factions, inline=False)

    embed.add_field(
        name="Impact Multiplier", value=data["impactMultiplier"], inline=False
    )

    return embed


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


campaign_types = {0: "Liberation / Defense", 1: "Recon", 2: "Story"}


def create_assignment_embed(
    data: Assignment2,
    last: Optional[Assignment2] = None,
    planets: Dict[int, Planet] = {},
):
    did, title = data["id"], data["title"]
    briefing = data["briefing"]
    embed = discord.Embed(
        title=f"Assignment A{did}:{title}",
        description=f"{briefing} ",
        color=0x0000FF,
    )

    progress = data["progress"]
    if last is not None:
        progress = [(t, l) for t, l in zip(data.progress, last.progress)]
    embed.add_field(name="Description", value=data["description"], inline=False)
    tasks = ""
    for e, task in enumerate(data["tasks"]):
        task_type = task_types.get(task["type"], "Unknown Task Type")
        taskdata = {"planet_index": "ERR", "race": 15}
        curr, last = progress[e]
        taskstr = f"[{e}]{task_type}: {hf(curr)}"
        for v, vt in zip(task["values"], task["valueTypes"]):
            # print(v, value_types.get(vt, "Unmapped vt"))
            taskdata[value_types[vt]] = v

        if task["type"] in (11, 13):
            planet_id = taskdata["planet_index"]
            planet_name = "ERR"
            health = "?"
            if int(planet_id) in planets:
                planet = planets[int(planet_id)]
                planet_name = planet.name
                health = planet.health_percent()
            taskstr = f"[{e}]{task_type}:{planet_name}({planet_id}) Status:{'ok' if curr==1 else f'{health},{curr}'}"

        elif task["type"] == 12:
            planet_name = taskdata["planet_index"]
            taskstr += f"{task['values'][0]} planets"
        elif task["type"] == 3:
            faction_name = faction_names.get(
                taskdata["race"], f"Unknown Faction {taskdata['race']}"
            )
            taskstr += f"/{hf(taskdata['goal'])} ({(int(curr)/int(taskdata['goal']))*100.0}){faction_name}"
        else:
            taskstr += f"DATA CORRUPTED.{json.dumps(task)[:50]}."
        tasks += taskstr + "\n"

    embed.add_field(name="Tasks", value=tasks, inline=False)

    embed.add_field(name="Reward", value=data.reward.format(), inline=False)
    exptime = et(data["expiration"])
    embed.add_field(name="Expiration", value=fdt(exptime, "f"), inline=False)

    return embed


def create_campaign_str(data):
    cid = data["id"]
    campaign_type = campaign_types.get(data["type"], "Unknown type")
    count = data["count"]
    output = f"C{cid}: {campaign_type}.  Op number:{count}"

    return output


def create_planet_embed(
    data: Planet, cstr: Campaign2, last: Planet = None, stat: ApiStatus = None
):
    """Create a detailed embed for a single planet."""
    cstri = ""
    if cstr:
        cstri = create_campaign_str(cstr)
    planet_index = data.get("index", "index error")
    planet_name = data.get("name", "Name error")
    stats = data.statistics
    stat_str = stats.format_statistics()
    if stats and (last is not None):
        stat_str = stats.diff_format(last.statistics)
    planet_sector = data.get("sector", "sector error")

    orig_owner = data.get("initialOwner", "?")
    curr_owner = data.get("currentOwner", "?")
    owner = f"{curr_owner} Control"
    if curr_owner != orig_owner:
        owner = f"{curr_owner} Occupation"
    embed = discord.Embed(
        title=f"{data.get_name()}",
        description=f"{planet_sector} Sector\n{owner}\n {stat_str}",
        color=0xFFA500,
    )
    embed.set_footer(text=cstri)
    embed.set_author(name=f"Planet Index {planet_index}")

    if data.biome:
        planet_biome = data["biome"]
        biome_name = planet_biome.get("name", "[GWW SEARCH ERROR]")
        biome_description = planet_biome.get("description", "No description available")
        embed.add_field(
            name=f"Biome:{biome_name}",
            value=f"{biome_description}",
            inline=False,
        )

    if data.hazards:
        planet_hazards = data["hazards"]
        hazards_str = ""
        for hazard in planet_hazards:
            hazard_name = hazard.get("name", "Unknown Hazard")
            hazard_description = hazard.get("description", "No description available")
            hazards_str += f"**{hazard_name}:** {hazard_description}\n"
        embed.add_field(name="Hazards", value=hazards_str, inline=False)

    max_health = data.get("maxHealth", 0)
    health = data.get("health", 0)
    if last and last.health != 0:
        embed.add_field(
            name="Health",
            value=f"`{health}/{max_health}`.  ({last.health} change)",
            inline=True,
        )
    else:
        embed.add_field(name="Health", value=f"`{health}/{max_health}`.  ", inline=True)

    regen_per_second = data.get("regenPerSecond", 0)
    needed_eps = regen_per_second / stat.war.get_first().impactMultiplier
    embed.add_field(
        name="Regeneration Per Second",
        value=f"`{regen_per_second}` .  \n Need `{round(needed_eps,2)}` eps",
        inline=True,
    )

    if cstr:
        lis = stat.campaigns.get(cstr.id)
        changes = lis.get_changes()
        avg = None
        if changes:
            avg = Planet.average([c.planet for c in changes])
        if avg:
            remaining_time = data.estimate_remaining_lib_time(avg)
            if remaining_time:
                embed.add_field(name="Est. Lib Time", value=f"{remaining_time}")

    event_info = data.get("event", None)

    if event_info:
        last_evt = None
        if last is not None and last.event is not None:
            last_evt = last.event
        event_details = event_info.long_event_details(last_evt)
        embed.add_field(name="Event Details", value=event_details, inline=False)

    # position = data.position
    # if position:
    #     x, y = position.get("x", 0), position.get("y", 0)
    #     embed.add_field(name="Galactic Position", value=f"x:{x},y:{y}", inline=True)

    if data.attacking:
        att = []
        for d in data.attacking:
            if int(d) in stat.planets:
                att.append(stat.planets[d].get_name())
        if att:
            embed.add_field(
                name="Attacking Planets",
                value=",  ".join(map(str, att)),
                inline=True,
            )
        else:
            embed.add_field(
                name="Attacking Planets", value="Not attacking planets.", inline=True
            )

    if data.waypoints:
        planet_waypoints = []
        for d in data.waypoints:
            if int(d) in stat.planets:
                planet_waypoints.append(stat.planets[d].get_name())
        if planet_waypoints:
            embed.add_field(
                name="Waypoints",
                value=", ".join(map(str, planet_waypoints)),
                inline=True,
            )
        else:
            embed.add_field(
                name="Waypoints",
                value="Planet appears to be unconnected.",
                inline=True,
            )

    return embed


def campaign_view(stat: ApiStatus, hdtext={}):
    flav = "Galactic Status."
    if "galactic_overview" in hdtext:

        flav = random.choice(hdtext["galactic_overview"]["value"])
    emb = discord.Embed(title="Galactic War Overview", description=f"{flav}\n")
    all_players, last = stat.war.get_first_change()
    change_war = all_players - last
    total = 0

    prop = defaultdict(int)
    for k, list in stat.campaigns.items():
        camp, last = list.get_first_change()
        changes = list.get_changes()
        this_faction = camp.planet.campaign_against()
        pc = camp.planet.statistics.playerCount
        prop[this_faction] += pc
        total += pc
        avg = None
        if changes:
            avg = Planet.average([c.planet for c in changes])
        name, desc = camp.planet.simple_planet_view((camp - last).planet, avg)
        features = get_feature_dictionary(stat, k)
        pred = make_prediction_for_eps(features)
        print(features["eps"], pred)
        eps_estimated = round(pred, 3)
        eps_real = round(features["eps"], 3)
        desc += f"\nExp/s:`{eps_estimated},c{eps_real}`"
        emb.add_field(name=name, value=desc, inline=True)
    emb.description += f"???:{all_players.statistics.playerCount-total}," + ",".join(
        [f"{k}:{v}" for k, v in prop.items()]
    )

    return emb
