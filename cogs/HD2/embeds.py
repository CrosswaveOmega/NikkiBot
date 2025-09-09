from typing import Dict, List, Optional, Union


import datetime
import discord

from hd2api.models import Campaign

from hd2api import Assignment2, Campaign2, Planet, SpaceStation, TacticalAction, Region
from hd2api.builders import get_time_dh
from hd2api.constants import items
from utility import count_total_embed_characters
import gui

"""
Collection of embeds for formatting.
"""
from collections import defaultdict
from discord.utils import format_dt as fdt

from hd2api import extract_timestamp as et, hdml_parse

import random
from .GameStatus import ApiStatus, get_feature_dictionary
from .predict import make_prediction_for_eps, predict_needed_players


item_emojis: Dict[str, str] = {
    897894480: "<:Medal:1241748215087235143>",
    3608481516: "<:rec:1274481505611288639>",
    3481751602: "<:supercredit:1274728715175067681>",
    2985106497: "<:RareSample:1306726016575607025>",
    3992382197: "<:CommonSample:1306726063233044591>",
}


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
        tasks += task.format_task_str(progress[e], e, planets) + "\n"

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
    fact = None
    if hasattr(data, "faction"):
        fact = data.faction
    else:
        fact = data.race

    output = f"C{cid}: {campaign_type}.  Op number:{count}, Faction:{fact}"

    return output


def create_planet_embed(
    data: Planet,
    cstr: Campaign2,
    last: Optional[Planet] = None,
    stat: Optional[ApiStatus] = None,
) -> discord.Embed:
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

    _add_biome_and_hazards(embed, data)
    _add_health_and_regen(embed, data, last, stat)
    _add_avg_and_estimated_time(embed, data, cstr, stat)
    _add_event_details(embed, data, last)
    _add_connections_and_attacks(embed, data, stat)
    _add_effects(embed, data)
    _add_regions(embed, data)

    return embed


def _add_biome_and_hazards(embed: discord.Embed, data: Planet) -> None:
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


def _add_health_and_regen(
    embed: discord.Embed,
    data: Planet,
    last: Optional[Planet],
    stat: Optional[ApiStatus],
) -> None:
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
        value=f"`{regen_per_second}` .  \n Need `{round(needed_eps, 2)}` eps and `{round(needed_players, 2)}` divers ",
        inline=True,
    )


def _add_avg_and_estimated_time(
    embed: discord.Embed,
    data: Planet,
    cstr: Campaign2,
    stat: Optional[ApiStatus],
) -> None:
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


def _add_event_details(
    embed: discord.Embed,
    data: Planet,
    last: Optional[Planet],
) -> None:
    event_info = data.get("event", None)
    if event_info:
        last_evt = None
        if last is not None and last.event is not None:
            last_evt = last.event
        event_details = event_info.long_event_details(last_evt)
        embed.add_field(name="Event Details", value=event_details, inline=False)
        avg = None
        if hasattr(data, "avg") and data.avg and data.avg.event:
            embed.add_field(
                name="Event Prediction",
                value=data.event.estimate_remaining_lib_time(data.avg.event),
                inline=False,
            )


def _add_connections_and_attacks(
    embed: discord.Embed,
    data: Planet,
    stat: Optional[ApiStatus],
) -> None:
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


def _add_effects(embed: discord.Embed, data: Planet) -> None:
    if data.activePlanetEffects:
        effect_str = ""
        for effect in data.activePlanetEffects:
            effect_name = effect.name
            effect_description = effect.description
            effect_str += f"**{effect_name}:** {effect_description}\n"
        embed.add_field(name="Effects", value=effect_str[:1020], inline=False)


def _add_regions(embed: discord.Embed, data: Planet) -> None:
    if data.regions:
        for region in data.regions:
            namev, outlist = region.simple_region_view()
            de = "\n".join(o for o in outlist)
            embed.add_field(name=namev, value=de[:1020], inline=False)


def campaign_view(
    stat: ApiStatus,
    hdtext: Optional[Dict[str, str]] = None,
    full: bool = False,
    show_stalemate: bool = True,
    simplify_city: bool = False,
    add_estimated_influence_per_second: bool = True,
) -> discord.Embed:
    """Create a view for the current game state."""
    # Set default flavor text
    flav = "Galactic Status."
    # Check if hdtext has a galactic overview and randomize flavor text if present
    if hdtext:
        if "galactic_overview" in hdtext:
            flav = random.choice(hdtext["galactic_overview"]["value"])
    # Create the initial Discord embed
    if not show_stalemate:
        flav = ""
    emb0 = discord.Embed(title="Galactic War Overview", description=f"{flav}\n")
    emb = emb0
    embs = [emb]
    # Get player information from the war status
    all_players, _ = stat.war.get_first_change()
    if all_players == None:
        emb0 = discord.Embed(
            title="Galactic War Overview",
            description=f"The war is disabled!  Please check back later.\n",
        )
        emb0.timestamp = discord.utils.utcnow()  # Set timestamp
        return [embs]
    total_contrib = [0, 0.0, 0.0, 0.0, 0.0]
    total, embed_list_length = 0, 0
    prop = defaultdict(int)
    stalemated = []
    allp = all_players.statistics.playerCount
    players_on_stalemated = 0
    # Iterate over each campaign in the status
    for k, list in sorted(
        stat.campaigns.items(),
        key=lambda item: item[1].get_first().planet.statistics.playerCount
        if item[1].get_first().planet is not None
        else 0,
        reverse=True,
    ):
        camp, last = list.get_change_from(15)
        changes = list.get_changes()
        if not camp.planet:
            continue
        this_faction = camp.planet.campaign_against()  # Determine opposing faction
        pc = camp.planet.statistics.playerCount
        prop[this_faction] += pc
        total += pc
        avg = None
        # Calculate average planet statistics
        if changes:
            avg = Planet.average([c.planet for c in changes[:4]])
        # Calculate difference in planet statistics
        planet_difference: Planet = (camp - last).planet
        name, desc = camp.planet.simple_planet_view(
            planet_difference, avg, full, show_city=True
        )
        desc = "\n".join(desc)
        # Skip stalemated planets if necessary
        r_act, r_ours, r_theirs = 0, 0, 0
        if simplify_city and "REGIONS" in desc:
            desc = desc.replace("Decay:", "⏷%")
            split = desc.split("**REGIONS")
            p1 = split[0]
            d2 = split[1]
            newdesc = ""
            ignore, owned, act, allregions = 0, 0, 0, len(camp.planet.regions)
            significant = True
            # Check if planet has a significant
            if (pc / allp) < 0.02:
                significant = False
            for reg in camp.planet.regions:
                if reg.isAvailable:
                    act += 1
                    r_act += 1
                else:
                    r_ours += int(reg.owner == 1)
                    r_theirs += int(reg.owner != 1)
                reg.inline_view()
                hpv = round((reg.health / max(reg.maxHealth, 1)) * 100, 1)
                if (reg.isAvailable and significant) or hpv < 100.0:
                    # eg, are they doing something.
                    newdesc += reg.inline_view() + "\n"
                elif reg.owner == 1:
                    owned += 1
                else:
                    ignore += 1
            if newdesc:
                newdesc = f"{p1}REGIONS\n{newdesc}"
                if ignore:
                    newdesc += f"{act}/{allregions} Active, {owned}:{ignore}"
                desc = newdesc
            else:
                desc = p1 + f"{act}/{allregions} Active, {owned}:{ignore}"

        if not show_stalemate:
            if "Stalemate" in desc and "REGIONS" not in desc:
                desc = desc.replace("Stalemate.\n", "")
                desc = desc.replace("HP `100.0% `\n", "")
                namew = name
                if camp.planet.regions:
                    namew += f"({r_act}:{r_ours}:{r_theirs})"
                stalemated.append((namew, camp.planet.statistics.playerCount))
                players_on_stalemated += camp.planet.statistics.playerCount
                continue
            elif "Stalemate" in desc:
                desc = desc.replace("Stalemate.\n", "")
                desc = desc.replace("HP `100.0% `\n", "")
            if "Settlement" in desc:
                desc = desc.replace("Settlement", "🏚️")
            if "MegaCity" in desc:
                desc = desc.replace("MegaCity", "🏙️")
            if "City" in desc:
                desc = desc.replace("City", "🏨")
            if "Town" in desc:
                desc = desc.replace("Town", "🏘️")
            if simplify_city:
                desc = desc.replace("Humans", "H")
                desc = desc.replace("Terminids", "🪲")
                desc = desc.replace("Automaton", "🤖")
                desc = desc.replace("Illuminate", "🦑")

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
        if add_estimated_influence_per_second:
            features = get_feature_dictionary(stat, k)
            pred = make_prediction_for_eps(features)
            eps_estimated = round(pred, 3)
            eps_real = round(features["eps"], 3)
            if not (eps_estimated <= 0 and eps_real <= 0):
                desc += f"\ninfl/s:`{eps_estimated},c{eps_real}`"
        # Manage embed field lengths
        if embed_list_length >= 24:
            emb = discord.Embed()
            embs.append(emb)
            embed_list_length = 0
        # Add fields to embed
        emb.add_field(name=name, value=desc, inline=True)
        embed_list_length += 1

    emb0.description += f"???:{all_players.statistics.playerCount - total}," + ",".join(
        [f"{k}:{v}" for k, v in prop.items()]
    )
    if stalemated:
        # Emoji mapping
        emojis = {
            "automaton": "<:bots:1241748819620659332>",
            "terminids": "<:bugs:1241748834632208395>",
            "humans": "<:superearth:1275126046869557361>",
            "illuminate": "<:squid:1274752443246448702>",
        }

        # Prepare lists
        automaton_list = []
        terminids_list = []
        humans_list = []
        illuminate_list = []
        other_list = []

        for s, pc in stalemated:
            if emojis["automaton"] in s:
                automaton_list.append(f"* {s.replace(emojis['automaton'], '')}`{pc}`")
            elif emojis["terminids"] in s:
                terminids_list.append(f"* {s.replace(emojis['terminids'], '')}`{pc}`")
            elif emojis["humans"] in s:
                humans_list.append(f"* {s.replace(emojis['humans'], '')}`{pc}`")
            elif emojis["illuminate"] in s:
                illuminate_list.append(f"* {s.replace(emojis['illuminate'], '')}`{pc}`")
            else:
                other_list.append(f"* {s}")

        stalemate_description = f"{players_on_stalemated} players are on {len(stalemated)} stalemated worlds.\n"
        # Add fields to embed
        emb.add_field(
            name="Planetary Stalemates", value=stalemate_description, inline=False
        )

        def add_chunks(name_orig, lines, emb):
            """helper function to chunk owned planets together."""
            name = f"{name_orig} ({len(lines)})"
            if not lines:
                return
            current_value = ""
            for line in lines:
                next_value = (
                    f"{current_value}{line}\n" if current_value else f"{line}\n"
                )
                if len(next_value) > 1000:
                    # Add fields to embed
                    emb.add_field(name=name, value=current_value.rstrip(), inline=True)
                    current_value = f"{line}\n"
                else:
                    current_value = next_value
            if current_value:
                # Add fields to embed
                emb.add_field(name=name, value=current_value.rstrip(), inline=True)
            return embed_list_length

        emb2 = discord.Embed()
        add_chunks("Automatons", automaton_list, emb2)
        add_chunks("Terminids", terminids_list, emb2)
        add_chunks("Illuminate", illuminate_list, emb2)
        add_chunks("Other", other_list, emb2)
        embs.append(emb2)

    # Add overall contribution stats
    emb0.description += (
        f"\n`{round((total_contrib[0] / all_players.statistics.playerCount) * 100.0, 4)}%` "
        f"divers contributed `{round(total_contrib[1], 4)}` visible Impact, which is "
        f"`{round(total_contrib[4], 8)}` impact per second, so about "
        f"`({round(total_contrib[2], 5)}%, {round(total_contrib[3], 5)}% per hour)` lib."
    )

    emb0.description += "\n"
    for k, list in stat.resources.items():
        r, c = list.get_change_from(15)
        changes = list.get_changes()
        # GET RATE OF CHANGE
        count = max(len(changes), 1)
        avg_value = (
            sum(res.currentValue for res in changes if res.currentValue is not None)
            // count
        )
        avg_time = (
            sum(
                res.time_delta.total_seconds()
                for res in changes
                if res.time_delta is not None
            )
            // count
        )
        rate = 0
        if avg_time > 0:
            rate = avg_value / avg_time
        cng = r - c
        outstring = f"{r.id32}:[`{r.currentValue}({cng.currentValue})/{r.maxValue}`,flags=`{r.flags}`] `Rate:{rate}`\n"
        emb0.description += outstring

    emb0.timestamp = discord.utils.utcnow()  # Set timestamp

    return embs


def generate_tactical_action_summary(stat, action: TacticalAction) -> str:
    """
    Returns a string summary for a TacticalAction object.
    """
    start = get_time_dh(stat.warall)
    exp = start + datetime.timedelta(seconds=action.statusExpireAtWarTimeSeconds)
    summary = []

    # Basic details
    title = action.name
    summary.append(f"Description:\n{action.description or 'No description provided.'}")
    summary.append(
        "\n"
        + hdml_parse(
            f"{action.strategicDescription or 'No strategic description provided.'}"
        )
    )
    sumv = f"Status: `{action.status or 'N/A'}`"

    # Status expiration
    if action.statusExpireAtWarTimeSeconds:
        sumv += " status expires" + fdt(exp, "R")

    summary.append(sumv)

    # Cost details
    if action.cost:
        for idx, cost in enumerate(action.cost, start=1):
            item = items.get(cost.itemMixId, cost.itemMixId)

            emj = item_emojis.get(cost.itemMixId, 897894480)
            cost_summary = f"\nItem {emj}`{item}`"
            remaining_sec = None
            percent = ""
            if cost.currentValue and cost.targetValue and cost.deltaPerSecond:
                diff = (cost.targetValue - cost.currentValue) / cost.deltaPerSecond
                remaining_sec = datetime.datetime.now() + datetime.timedelta(
                    seconds=diff
                )

            if cost.currentValue and cost.targetValue:
                num = round((cost.currentValue / cost.targetValue) * 100.0, 2)
                percent = f"{num:.2f}%"

            cost_summary += (
                f", at `{cost.currentValue}/{cost.targetValue or 'None'}`, {percent}"
                f" by `{cost.deltaPerSecond * 3600 or 'N/A'}` per hour"
            )
            if remaining_sec:
                cost_summary += f"\nComplete in {fdt(remaining_sec, 'R')}"
            cost_summary += f"\nMax Donation Amount: `{cost.maxDonationAmount or 'N/A'} per {cost.maxDonationPeriodSeconds / 3600 or 'N/A'} hours`"
            summary.append(cost_summary)
    else:
        summary.append("No cost details available.")

    # Effect IDs
    if action.effectIds:
        summary.append(f"Effect IDs:`[{', '.join(map(str, action.effectIds))}]`")
    # Active Effect IDs
    if action.activeEffectIds:
        summary.append(
            f"Active Effect IDs: `[{', '.join(map(str, action.activeEffectIds))}]`"
        )

    return title, "\n".join(summary)


def station_embed(stat: ApiStatus, station: SpaceStation) -> discord.Embed:
    # Create the initial Discord embed
    voting_exp = get_time_dh(stat.warall) + (
        datetime.timedelta(seconds=station.currentElectionEndWarTime)
    )
    endvote = fdt(voting_exp, "R")

    planet_name = station.planetIndex
    planet = stat.planets.get(station.planetIndex, None)
    if planet:
        planet_name = planet.get_name()

    embed = discord.Embed(
        title="Station Overview", description=f"Hovering over {planet_name}\n"
    )

    # Tactical Action Strings
    strs = []
    for t in station.tacticalActions:
        title, stri = generate_tactical_action_summary(stat, t)
        embed.add_field(name=title, value=stri[:1200], inline=False)
    embed.add_field(name="Next Voting Period", value=f"{endvote}")
    embed.set_footer(text=f"Flags={station.flags}")
    return embed


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
    total_contrib = [0, 0.0, 0.0, 0.0, 0.0]
    total = 0
    embed_list_length = 0
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

        embed_list_length += 1
    out_main += f"???:{all_players.statistics.playerCount - total}," + ",".join(
        [f"{k}:{v}" for k, v in prop.items()]
    )

    out_main += (
        f"\n`{round((total_contrib[0] / all_players.statistics.playerCount) * 100.0, 4)}%` "
        f"divers contributed `{round(total_contrib[1], 4)}` visible Impact, which is "
        f"`{round(total_contrib[4], 8)}` impact per second, so about "
        f"`({round(total_contrib[2], 5)}%, {round(total_contrib[3], 5)}% per hour)` lib."
    )
    lib_join = "\n".join([f"* {c[0]}\n{c[1]}" for c in liberation_campaigns])
    def_join = "\n".join([f"* {c[0]}\n{c[1]}" for c in defense_campaigns])
    out_main += f"\n **Liberation Campaigns:**\n{lib_join}\n**Defense Campaigns:**\n{def_join}\n"
    if stalemated:
        st = (
            f"{players_on_stalemated} players are on {len(stalemated)} stalemated worlds.\n"
            + ("\n".join([f"* {s}" for s in stalemated]))
        )
        out_main += "**Planetary Stalemates:**\n" + st

    return out_main


def region_view(
    stat,
    planet: Planet,
    hdtext: Optional[Dict[str, str]] = None,
    full: bool = False,
    show_stalemate: bool = True,
) -> List[discord.Embed]:
    flav = "Regional Status"
    planetIndex = planet.index

    if hdtext and "planetary_overview" in hdtext:
        flav = random.choice(hdtext["planetary_overview"]["value"])

    emb0 = discord.Embed(
        title=f"Planetary Region Status (#{planetIndex})",
        description=f"{flav}\n",
    )
    emb = emb0
    embs = [emb]

    if stat.war is None:
        emb0.description += "The war is disabled! Please check back later."
        emb0.timestamp = discord.utils.utcnow()
        return embs

    total_contrib = [0, 0.0, 0.0, 0.0, 0.0]  # playerCount, rate, %, %/hr, eps
    total = 0
    embed_list_length = 0
    prop = defaultdict(int)
    stalemated = []
    players_on_stalemated = 0
    allids = [int(p.id) for p in planet.regions]

    # Filter to regions for this planetIndex
    regions = {k: v for k, v in stat.regions.items() if int(k) in allids}

    for key, region_list in regions.items():
        reg, last = region_list.get_change_from(15)
        changes = region_list.get_changes()
        pc = reg.players
        total += pc
        avg = Region.average(changes[:4]) if changes else None
        diff: Region = reg - last
        name, desc = reg.simple_region_view(diff, avg)

        if embed_list_length >= 24:
            emb = discord.Embed()
            embs.append(emb)
            embed_list_length = 0

        emb.add_field(name=name, value="\n".join(desc), inline=False)
        embed_list_length += 1

    if stalemated:
        emb.add_field(
            name="Stalemated Regions",
            value=f"{players_on_stalemated} players are on {len(stalemated)} stalemated regions.\n"
            + ("\n".join([f"* {s}" for s in stalemated]))[:900],
        )

    # Contribution summary
    try:
        all_players, _ = stat.war.get_first_change()
        if all_players:
            emb0.description += (
                f"\n`{round((total_contrib[0] / all_players.statistics.playerCount) * 100.0, 4)}%` "
                f"divers contributed `{round(total_contrib[1], 4)}` visible Impact, "
                f"`{round(total_contrib[4], 8)}` impact/sec → "
                f"`({round(total_contrib[2], 5)}%, {round(total_contrib[3], 5)}%/hr)` lib."
            )
    except Exception:
        emb0.description += "\n[Unable to calculate global contribution summary]"

    emb0.timestamp = discord.utils.utcnow()
    return embs
