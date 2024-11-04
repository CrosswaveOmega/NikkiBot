import json
from typing import Dict, List, Optional, Tuple, Union


import datetime
import os
import discord

from hd2api.models import Campaign

from hd2api import Assignment2, Campaign2, Planet, War, GlobalEvent, PlanetAttack

"""
Collection of embeds for formatting.
"""
from collections import defaultdict
import re
from discord.utils import format_dt as fdt

from hd2api import extract_timestamp as et, hdml_parse

import random
from .GameStatus import ApiStatus, get_feature_dictionary
from .predict import make_prediction_for_eps, predict_needed_players


def create_war_embed(stat: ApiStatus):
    data, last = stat.war.get_first_change()
    stats = data["statistics"]
    stat_str = data.statistics.format_statistics()
    if stats and (last is not None):
        stat_str = stats.diff_format(stats - last.statistics)
    globtex = ""
    if stat.warall:
        for evt in stat.warall.status.globalEvents:
            if evt.title and evt.message:
                mes = hdml_parse(evt.message)
                globtex += f"### {evt.title}\n{mes}\n\n"
    embed = discord.Embed(
        title="War", description=f"{globtex}\n{stat_str}"[:4096], color=0xFF0000
    )

    embed.add_field(name="Started", value=fdt(et(data["started"]), "F"), inline=True)
    embed.add_field(name="Ended", value=fdt(et(data["ended"]), "F"), inline=True)
    embed.add_field(name="Now", value=fdt(data.retrieved_at, "F"), inline=True)

    factions = ", ".join(data["factions"])
    embed.add_field(name="Factions", value=factions, inline=False)
    embed.add_field(name="Client Version", value=data["clientVersion"], inline=True)

    embed.add_field(
        name="Impact Multiplier", value=data["impactMultiplier"], inline=True
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
        title=f"{title}",
        description=f"{briefing} ",
        color=0x0000FF,
    )
    embed.set_author(name=f"Assignment A#{did}")
    diff, rates = None, []
    exptime = et(data["expiration"])
    time_remaining = (exptime - data.retrieved_at).total_seconds()
    if data and last:
        diff = last.progress if last.progress else []
        seconds = last.time_delta.total_seconds()
        if seconds > 0:
            rates = [i / seconds for i in diff]
        else:
            rates = [i / 1 for i in diff]

    progress = data.progress
    embed.add_field(name="Objective", value=data["description"], inline=False)
    tasks = ""
    if data.flags == 2:
        tasks += "Complete any one task to win.\n"
    for e, task in enumerate(data.tasks):
        chg, projected = None, None
        prog = ""
        if diff and isinstance(diff, list):
            if e < len(diff):
                chg = diff[e]
                projected = progress[e] + (rates[e] * time_remaining)
        tasks += task.task_str(progress[e], e, planets, chg, projected) + "\n"

    embed.add_field(name="Tasks", value=tasks, inline=False)
    if data.rewards:
        for e, d in enumerate(data.rewards):
            embed.add_field(name=f"Reward {e}", value=d.format(), inline=True)
    else:
        embed.add_field(name="Reward", value=data.reward.format(), inline=True)

    embed.add_field(name="Expiration", value=fdt(exptime, "f"), inline=True)
    embed.set_footer(text=f"Flags={data.flags}, type={data.type}")

    return embed


def create_campaign_str(data: Union[Campaign2, Campaign]) -> str:
    cid = data["id"]
    campaign_type = campaign_types.get(data["type"], f"Unknown type {data.type}")
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
        embed.add_field(
            name=f"Biome: {data.biome.name}",
            value=f"{data.biome.description}",
            inline=False,
        )

    if data.hazards:
        hazards_str = ""
        for hazard in data.hazards:
            hazard_name = hazard.name
            hazard_description = hazard.description
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
    mp_mult = stat.war.get_first().impactMultiplier
    needed_eps = regen_per_second / mp_mult

    needed_players, _ = predict_needed_players(needed_eps, mp_mult)
    embed.add_field(
        name="Regeneration Per Second",
        value=f"`{regen_per_second}` .  \n Need `{round(needed_eps,2)}` eps and `{round(needed_players,2)}` divers ",
        inline=True,
    )
    avg = None
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
        if avg:
            if avg.event:
                embed.add_field(
                    name="Event Prediction",
                    value=data.event.estimate_remaining_lib_time(avg.event),
                    inline=False,
                )

    # position = data.position
    # if position:
    #     x, y = position.get("x", 0), position.get("y", 0)
    #     embed.add_field(name="Galactic Position", value=f"x:{x},y:{y}", inline=True)

    planet_connections = []
    under_attack_by = []
    for i, v in stat.planets.items():
        for d in v.waypoints:
            if int(d) == data.index:
                planet_connections.append(v.get_name())
        for d in v.attacking:
            if int(d) == data.index:
                under_attack_by.append(v.get_name())

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

    if under_attack_by:
        embed.add_field(
            name="Under Attack From",
            value=", ".join(map(str, under_attack_by)),
            inline=True,
        )

    if data.waypoints:
        planet_waypoints = []
        for d in data.waypoints:
            if int(d) in stat.planets:
                planet_waypoints.append(stat.planets[d].get_name())
        if planet_waypoints:
            embed.add_field(
                name="Waypoints Leading Out",
                value=", ".join(map(str, planet_waypoints)),
                inline=True,
            )
        else:
            embed.add_field(
                name="Waypoints",
                value="Planet has no waypoints.",
                inline=True,
            )

    if planet_connections:
        embed.add_field(
            name="Waypoints Leading In",
            value=", ".join(map(str, planet_connections)),
            inline=True,
        )

    if data.activePlanetEffects:
        effect_str = ""
        for effect in data.activePlanetEffects:
            effect_name = effect.name
            effect_description = effect.description
            effect_str += f"**{effect_name}:** {effect_description}\n"
        embed.add_field(name="Effects", value=effect_str[:1020], inline=False)

    return embed


def campaign_view(
    stat: ApiStatus,
    hdtext: Optional[Dict[str, str]] = None,
    full: bool = False,
    show_stalemate: bool = True,
):
    # Set default flavor text
    flav = "Galactic Status."
    # Check if hdtext has a galactic overview and randomize flavor text if present
    if hdtext:
        if "galactic_overview" in hdtext:
            flav = random.choice(hdtext["galactic_overview"]["value"])
    # Create the initial Discord embed
    emb0 = discord.Embed(title="Galactic War Overview", description=f"{flav}\n")
    emb = emb0
    embs = [emb]
    # Get player information from the war status
    all_players, last = stat.war.get_first_change()
    change_war = all_players - last
    total_contrib = [0, 0.0, 0.0, 0.0, 0.0]
    total = 0
    el = 0
    prop = defaultdict(int)
    stalemated = []
    players_on_stalemated = 0
    # Iterate over each campaign in the status
    for k, list in stat.campaigns.items():
        camp, last = list.get_first_change()
        changes = list.get_changes()
        this_faction = camp.planet.campaign_against()  # Determine opposing faction
        pc = camp.planet.statistics.playerCount
        prop[this_faction] += pc
        total += pc
        avg = None
        # Calculate average planet statistics
        if changes:
            avg = Planet.average([c.planet for c in changes])
        # Calculate difference in planet statistics
        planet_difference: Planet = (camp - last).planet
        name, desc = camp.planet.simple_planet_view(planet_difference, avg, full)
        desc = "\n".join(desc)
        # Skip stalemated planets if necessary
        if not show_stalemate:
            if "Stalemate" in desc:
                stalemated.append(name)
                players_on_stalemated += camp.planet.statistics.playerCount
                continue

        if planet_difference.event != None:
            p_evt = planet_difference.event
            if isinstance(p_evt.time_delta, datetime.timedelta):
                total_sec = (
                    p_evt.time_delta.total_seconds()
                )  # Convert timedelta to seconds
                if total_sec == 0:
                    continue
                # Calculate contribution rates
                rate = -1 * (p_evt.health)
                total_contrib[0] += camp.planet.statistics.playerCount
                total_contrib[1] += rate
                thisamt = round((rate / camp.planet.maxHealth) * 100.0, 5)
                total_contrib[2] += thisamt
                total_contrib[3] += round(
                    (thisamt / max(1, total_sec)) * 60 * 60, 5
                )  # Contribution per hour
                total_contrib[4] += rate / total_sec  # Impact per second

        elif planet_difference.health_percent() != 0:
            if isinstance(planet_difference.time_delta, datetime.timedelta):
                total_sec = (
                    planet_difference.time_delta.total_seconds()
                )  # Convert timedelta to seconds
                if total_sec == 0:
                    continue
                # Calculate contribution rates
                rate = (-1 * (planet_difference.health)) + (
                    (camp.planet.regenPerSecond) * total_sec
                )
                total_contrib[0] += camp.planet.statistics.playerCount
                total_contrib[1] += rate
                thisamt = round((rate / camp.planet.maxHealth) * 100.0, 5)
                total_contrib[2] += thisamt
                total_contrib[3] += round(
                    (thisamt / total_sec) * 60 * 60, 5
                )  # Contribution per hour
                total_contrib[4] += rate / total_sec  # Impact per second

        # Get estimated and real EPS
        features = get_feature_dictionary(stat, k)
        pred = make_prediction_for_eps(features)
        eps_estimated = round(pred, 3)
        eps_real = round(features["eps"], 3)
        desc += f"\ninfl/s:`{eps_estimated},c{eps_real}`"
        # Manage embed field lengths
        if el >= 24:
            emb = discord.Embed()
            embs.append(emb)
            el = 0
        # Add fields to embed
        emb.add_field(name=name, value=desc, inline=True)
        el += 1

    emb0.description += f"???:{all_players.statistics.playerCount-total}," + ",".join(
        [f"{k}:{v}" for k, v in prop.items()]
    )
    if stalemated:
        # Add information about stalemated planets
        emb.add_field(
            name="Planetary Stalemates",
            value=f"{players_on_stalemated} players are on {len(stalemated)} stalemated worlds.\n"
            + (f"\n".join([f"* {s}" for s in stalemated]))[:900],
        )
    # Add overall contribution stats
    emb0.description += (
        f"\n`{round((total_contrib[0]/all_players.statistics.playerCount)*100.0, 4)}%` "
        f"divers contributed `{round(total_contrib[1], 4)}` visible Impact, which is "
        f"`{round(total_contrib[4],8)}` impact per second, so about "
        f"`({round(total_contrib[2],5)}%, {round(total_contrib[3],5)}% per hour)` lib."
    )
    emb0.timestamp = discord.utils.utcnow()  # Set timestamp
    return embs


def campaign_text_view(
    stat: ApiStatus,
    hdtext: Optional[Dict[str, str]] = None,
    full: bool = False,
    show_stalemate: bool = True,
) -> str:
    flav = "Galactic Status."
    if hdtext:
        if "galactic_overview" in hdtext:
            flav = random.choice(hdtext["galactic_overview"]["value"])

    out_main = "**Current galactic war overview.**\n\n Objective for Liberation Campaigns is to reduce HP to zero."
    out_main += "\n A negative DPS is good for us, a positive one means we are losing on that world."
    out_main += "\n Objective for Defense Campaigns is to reduce EventHP to zero before the deadline.\n"

    all_players, last = stat.war.get_first_change()
    change_war = all_players - last
    total_contrib = [0, 0.0, 0.0, 0.0]
    total = 0
    el = 0
    prop = defaultdict(int)
    stalemated = []
    players_on_stalemated = 0
    liberation_campaigns = []
    defense_campaigns = []
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
        planet_difference: Planet = (camp - last).planet
        name, desc = camp.planet.simple_planet_view(planet_difference, avg, full)
        desc = "\n".join(f"  * {m}" for m in desc)
        if not show_stalemate:
            if "Stalemate" in desc:
                stalemated.append(name)
                players_on_stalemated += camp.planet.statistics.playerCount
                continue

        if planet_difference.event != None:
            p_evt = planet_difference.event
            if isinstance(p_evt.retrieved_at, datetime.timedelta):
                total_sec = (
                    p_evt.time_delta.total_seconds()
                )  # Convert timedelta to seconds
                if total_sec == 0:
                    continue
                # Calculate contribution rates
                rate = -1 * (p_evt.health)
                total_contrib[0] += camp.planet.statistics.playerCount
                total_contrib[1] += rate
                thisamt = round((rate / camp.planet.maxHealth) * 100.0, 5)
                total_contrib[2] += thisamt
                total_contrib[3] += round(
                    (thisamt / max(1, total_sec)) * 60 * 60, 5
                )  # Contribution per hour
                total_contrib[4] += rate / total_sec  # Impact per second

        elif planet_difference.health_percent() != 0:
            if isinstance(planet_difference.retrieved_at, datetime.timedelta):
                total_sec = (
                    planet_difference.time_delta.total_seconds()
                )  # Convert timedelta to seconds
                if total_sec == 0:
                    continue
                # Calculate contribution rates
                rate = (-1 * (planet_difference.health)) + (
                    (camp.planet.regenPerSecond) * total_sec
                )
                total_contrib[0] += camp.planet.statistics.playerCount
                total_contrib[1] += rate
                thisamt = round((rate / camp.planet.maxHealth) * 100.0, 5)
                total_contrib[2] += thisamt
                total_contrib[3] += round(
                    (thisamt / total_sec) * 60 * 60, 5
                )  # Contribution per hour
                total_contrib[4] += rate / total_sec  # Impact per second

        features = get_feature_dictionary(stat, k)
        pred = make_prediction_for_eps(features)
        # print(features["eps"], pred)
        eps_estimated = round(pred, 3)
        eps_real = round(features["eps"], 3)
        desc += f"\n  * infl/s:`{eps_estimated},c{eps_real}`"
        if camp.planet.event:
            defense_campaigns.append((name, desc))
        else:
            liberation_campaigns.append((name, desc))

        el += 1
    out_main += f"???:{all_players.statistics.playerCount-total}," + ",".join(
        [f"{k}:{v}" for k, v in prop.items()]
    )

    out_main += (
        f"\n`{round((total_contrib[0]/all_players.statistics.playerCount)*100.0, 4)}%` "
        f"divers contributed `{round(total_contrib[1], 4)}` visible Impact, which is "
        f"`{round(total_contrib[4],8)}` impact per second, so about "
        f"`({round(total_contrib[2],5)}%, {round(total_contrib[3],5)}% per hour)` lib."
    )
    lib_join = "\n".join([f"* {c[0]}\n{c[1]}" for c in liberation_campaigns])
    def_join = "\n".join([f"* {c[0]}\n{c[1]}" for c in defense_campaigns])
    out_main += f"\n **Liberation Campaigns:**\n{lib_join}\n**Defense Campaigns:**\n{def_join}\n"
    if stalemated:
        st = (
            f"{players_on_stalemated} players are on {len(stalemated)} stalemated worlds.\n"
            + (f"\n".join([f"* {s}" for s in stalemated]))
        )
        out_main += f"**Planetary Stalemates:**\n" + st

    return out_main
