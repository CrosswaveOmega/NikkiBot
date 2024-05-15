from typing import Dict, List, Tuple
import discord
import json
from .helldive import Planet,War,Assignment2, Campaign2
'''
Collection of embeds for formatting.
'''


from utility import human_format as hf, select_emoji as emj, changeformatif as cfi, extract_timestamp as et
from discord.utils import format_dt as fdt

def create_war_embed(data, last=None):
    stats = data["statistics"]
    stat_str = data.statistics.format_statistics()
    if stats and (last is not None):
        stat_str = stats.diff_format(stats-last.statistics)

    embed = discord.Embed(title="War", description=f"{stat_str}", color=0xFF0000)

    embed.add_field(name="Started", value=fdt(et(data["started"]),'F'), inline=False)
    embed.add_field(name="Ended", value=fdt(et(data["ended"]),'F'), inline=False)
    embed.add_field(name="Now", value=fdt(et(data["now"]),'F'), inline=False)
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
    1: "Humans",
    2: "Terminids",
    3: "Automaton",
    4: "Illuminate",
    5: "ERR",
    15: "ERR",
}


campaign_types = {0: "Liberation / Defense", 1: "Recon", 2: "Story"}


def create_assignment_embed(data,last=None,planets:Dict[int,Planet]={}):
    did, title = data["id"], data["title"]
    briefing = data["briefing"]
    embed = discord.Embed(
        title=f"Assignment A{did}:{title}",
        description=f"{briefing} ",
        color=0x0000FF,
    )

    progress = data["progress"]
    if (last is not None):
        progress=[(t,l) for t, l in zip(data.progress, last.progress)]
    embed.add_field(name="Description", value=data["description"], inline=False)
    tasks = ""
    for e, task in enumerate(data["tasks"]):
        task_type = task_types.get(task["type"], "Unknown Task Type")
        taskdata = {"planet_index": "ERR", "race": 15}
        curr,last=progress[e]
        taskstr = f"[{e}]{task_type}: p {curr},"
        for v, vt in zip(task["values"], task["valueTypes"]):
            #print(v, value_types.get(vt, "Unmapped vt"))
            taskdata[value_types[vt]] = v

        if task["type"] in (11, 13):
            planet_name = taskdata["planet_index"]
            if int(planet_name) in planets:
                planet_name=planets[int(planet_name)].name
            taskstr += f"{planet_name}"
        elif task["type"] == 12:
            planet_name = taskdata["planet_index"]
            taskstr += f"{task['values'][0]} planets"
        elif task["type"] == 3:
            faction_name = faction_names.get(taskdata["race"], "Unknown Faction")
            taskstr += f"{taskdata['goal']} ({(int(curr)/int(taskdata['goal']))*100.0}){faction_name}"
        else:
            taskstr += f"DATA CORRUPTED.{json.dumps(task)[:50]}."
        tasks += taskstr + "\n"

    embed.add_field(name="Tasks", value=tasks, inline=False)

    embed.add_field(name="Reward", value=data["reward"], inline=False)
    embed.add_field(name="Expiration", value=data["expiration"], inline=False)

    return embed


def create_campaign_str(data):
    cid = data["id"]
    campaign_type = campaign_types.get(data["type"], "Unknown type")
    count = campaign_types.get(data["count"], 0)
    output = f"C{cid}: {campaign_type}.  Op number:{count}"

    return output


def create_planet_embed(data:Planet, cstr: str,last:Planet=None):
    '''Create a detailed embed for a single planet.'''
    planet_index = data.get("index", "index error")
    planet_name = data.get("name", "Name error")
    stats = data.get("statistics", None)
    stat_str = stats.format_statistics()
    if stats and (last is not None):
        stat_str = stats.diff_format(last.statistics)
    planet_sector = data.get("sector", "sector error")
    embed = discord.Embed(
        title=f"Planet: {planet_name}",
        description=f"{planet_sector}, {stat_str}",
        color=0xFFA500,
    )
    embed.set_footer(text=cstr)
    embed.set_author(name=f"Planet Index {planet_index}")

    if data.biome:
        planet_biome = data["biome"]
        biome_name = planet_biome.get("name", "Unknown Biome")
        biome_description = planet_biome.get("description", "No description available")
        embed.add_field(
            name="Biome",
            value=f"Name: {biome_name}\nDescription: {biome_description}",
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

    orig_owner = data.get("initialOwner", "?")
    curr_owner = data.get("currentOwner", "?")
    string = f"{orig_owner}, {curr_owner}"
    if orig_owner == curr_owner:
        string = orig_owner
    if curr_owner != orig_owner:
        string = f"{orig_owner}  occupied by {curr_owner}"
    embed.add_field(name="Ownership", value=string, inline=True)

    regen_per_second = data.get("regenPerSecond", 0)
    embed.add_field(name="Regeneration Per Second", value=regen_per_second, inline=True)

    max_health = data.get("maxHealth", 0)
    health = data.get("health", 0)
    if last:
        embed.add_field(name="Health", value=f"{health}/{max_health}.  ({last.health} change)", inline=True)
    else:
        embed.add_field(name="Health", value=f"{health}/{max_health}.  ", inline=True)



    event_info = data.get("event", None)

    if event_info:
        event_details = (
            f"ID: {(event_info['id'])}, Type: {hf(event_info['eventType'])}, Faction: {event_info['faction']}\n"
            f"Max Health: {hf(event_info['maxHealth'])}, Health: {hf(event_info['health'])}\n"
            f"Start Time: {fdt(et(event_info['startTime']),'R')}, End Time: {fdt(et(event_info['endTime']),'R')}\n"
            f"Campaign ID: {hf(event_info['campaignId'])}, Joint Operation IDs: {', '.join(map(str, event_info['jointOperationIds']))}"
        )
        if last:
            if last.event:
                event_details = (
                    f"ID: {(event_info['id'])}, Type: {hf(event_info['eventType'])}, Faction: {event_info['faction']}\n"
                    f"Max Health: {hf(event_info['maxHealth'])}, Health: {hf(event_info['health'])}({hf(last.event.health)})\n"
                    f"Start Time: {fdt(et(event_info['startTime']),'R')}, End Time: {fdt(et(event_info['endTime']),'R')}\n"
                    f"Campaign ID: {hf(event_info['campaignId'])}, Joint Operation IDs: {', '.join(map(str, event_info['jointOperationIds']))}"
                )
        embed.add_field(name="Event Details", value=event_details, inline=False)
    position = data.get("position", None)
    if position:
        x, y = position.get("x", 0), position.get("y", 0)
        embed.add_field(name="Galactic Position", value=f"x:{x},y:{y}", inline=True)

    if data.attacking:
        attacking_planets = data["attacking"]
        if attacking_planets:
            embed.add_field(
                name="Attacking Planets",
                value=", ".join(map(str, attacking_planets)),
                inline=True,
            )
        else:
            embed.add_field(
                name="Attacking Planets", value="Not attacking planets.", inline=True
            )

    if data.waypoints:
        planet_waypoints = data["waypoints"]
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

def campaign_view(campaigns:List[Tuple[Campaign2,Campaign2]]):
    emb=discord.Embed(title="Super Earth's Campaign",
                      description="As of right now, this is the current status of all planets in need of liberation or defence.")
    for last,camp in campaigns:
        diff=camp-last
        name,desc=camp.planet.simple_planet_view(diff.planet)
        emb.add_field(name=name,value=desc,inline=True)
    return emb