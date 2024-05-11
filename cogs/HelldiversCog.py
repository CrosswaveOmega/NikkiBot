import json
from typing import Literal
import gui
import discord
from discord import app_commands

from discord.ext import commands, tasks

# import datetime
from bot import (
    TCBot,
    TC_Cog_Mixin,
)
from discord.ext import commands
from .HD2.hdapi import call_api, human_format


def format_statistics(statistics):
    # Format mission statistics
    mission_stats = f"W:{human_format(statistics.get('missionsWon', 0))},"
    mission_stats += f"L:{human_format(statistics.get('missionsLost', 0))}"
    # mission_stats += f"Time: {human_format(statistics.get('missionTime', 0))} seconds"

    # Format kill statistics
    kill_stats = (
        f"T:{human_format(statistics.get('terminidKills', 0))}, "
        f"A:{human_format(statistics.get('automatonKills', 0))}, "
        f"DATA EXPUNGED"
    )
    #             f"I: {human_format(statistics.get('illuminateKills', 0))}"

    # Format bullets statistics
    bullets_fired = statistics.get("bulletsFired", 0)
    bullets_hit = statistics.get("bulletsHit", 0)
    bullets_stats = (
        f"Bullets: {human_format(bullets_hit)}/{human_format(bullets_fired)}"
    )

    # Format deaths and friendlies statistics
    deaths_and_friendlies = (
        f"Deaths/Friendlies: {human_format(statistics.get('deaths', 0))}/"
        f"{human_format(statistics.get('friendlies', 0))}"
    )

    # Format mission success rate
    mission_success_rate = f"MCR: {statistics.get('missionSuccessRate', 0)}%"

    # Format accuracy
    accuracy = f"ACC: {statistics.get('accuracy', 0)}%"

    # Format player count
    player_count = f"Player Count: {human_format(statistics.get('playerCount', 0))}"

    # Concatenate all formatted statistics
    statsa = f"`[Missions: {mission_stats}] [Kills: {kill_stats}] [{bullets_stats}]`"
    statsb = f"`[{deaths_and_friendlies}] [{mission_success_rate}] [{accuracy}]`"

    return f"{player_count}\n{statsa}\n{statsb}"


def create_war_embed(data):
    stats = data.get("statistics", None)
    stat_str = ""
    if stats:
        stat_str = format_statistics(stats)
    embed = discord.Embed(title="War", description=f"{stat_str}", color=0xFF0000)

    embed.add_field(name="Started", value=data["started"], inline=False)
    embed.add_field(name="Ended", value=data["ended"], inline=False)
    embed.add_field(name="Now", value=data["now"], inline=False)
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


def create_assignment_embed(data):
    did, title = data["id"], data["title"]
    briefing = data["briefing"]
    embed = discord.Embed(
        title=f"Assignment A{did}:{title}",
        description=f"{briefing} ",
        color=0x0000FF,
    )

    progress = data["progress"]
    embed.add_field(name="Description", value=data["description"], inline=False)
    tasks = ""
    for e, task in enumerate(data["tasks"]):
        task_type = task_types.get(task["type"], "Unknown Task Type")
        taskdata = {"planet_index": "ERR", "race": 15}
        taskstr = f"[{e}]{task_type}: p {progress[e]},"
        for v, vt in zip(task["values"], task["valueTypes"]):
            print(v, value_types.get(vt, "Unmapped vt"))
            taskdata[value_types[vt]] = v

        if task["type"] in (11, 13):
            planet_name = taskdata["planet_index"]
            taskstr += f"{planet_name}"
        elif task["type"] == 12:
            planet_name = taskdata["planet_index"]
            taskstr += f"{task['values'][0]} planets"
        elif task["type"] == 3:
            faction_name = faction_names.get(taskdata["race"], "Unknown Faction")
            taskstr += f"{taskdata['goal']} {faction_name}"
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
    output = f"C{cid}: {campaign_type}.  planetary op:{count}"

    return output


def create_planet_embed(data, cstr: str):
    planet_index = data.get("index", "index error")
    planet_name = data.get("name", "Name error")
    stats = data.get("statistics", None)
    stat_str = ""
    if stats:
        stat_str = format_statistics(stats)
    planet_sector = data.get("sector", "sector error")
    embed = discord.Embed(
        title=f"Planet: {planet_name}",
        description=f"{planet_sector}, {stat_str}",
        color=0xFFA500,
    )
    embed.set_footer(text=cstr)
    embed.set_author(name=f"Planet Index {planet_index}")

    if "biome" in data:
        planet_biome = data["biome"]
        biome_name = planet_biome.get("name", "Unknown Biome")
        biome_description = planet_biome.get("description", "No description available")
        embed.add_field(
            name="Biome",
            value=f"Name: {biome_name}\nDescription: {biome_description}",
            inline=False,
        )

    if "hazards" in data:
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
    embed.add_field(name="Health", value=f"{health}/{max_health}.  ", inline=True)


    event_info = data.get("event", None)

    if event_info:
        event_details = (
            f"ID: {(event_info['id'])}, Type: {human_format(event_info['eventType'])}, Faction: {event_info['faction']}\n"
            f"Max Health: {human_format(event_info['maxHealth'])}, Health: {human_format(event_info['health'])}\n"
            f"Start Time: {event_info['startTime']}, End Time: {event_info['endTime']}\n"
            f"Campaign ID: {human_format(event_info['campaignId'])}, Joint Operation IDs: {', '.join(map(str, event_info['jointOperationIds']))}"
        )
        embed.add_field(name="Event Details", value=event_details, inline=False)
    position = data.get("position", None)
    if position:
        x, y = position.get("x", 0), position.get("y", 0)
        embed.add_field(name="Galactic Position", value=f"x:{x},y:{y}", inline=True)

    if "attacking" in data:
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

    if "waypoints" in data:
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


class HelldiversCog(commands.Cog, TC_Cog_Mixin):
    """cog for helldivers 2.  Consider it my embedded automaton spy."""

    def __init__(self, bot):
        self.bot: TCBot = bot
        # self.session=aiohttp.ClientSession()
        self.apidata = {}
        self.update_api.start()

    def cog_unload(self):
        self.update_api.cancel()

    @tasks.loop(minutes=15)
    async def update_api(self):
        try:
            war = await call_api("war")
            assignments = await call_api("assignments")
            campaigns = await call_api("campaigns")
            self.apidata["war"] = war
            self.apidata["assignments"] = assignments
            self.apidata["campaigns"] = campaigns

        except Exception as e:
            await self.bot.send_error(e, f"Message update cleanup error.")
            gui.gprint(str(e))
    pc = app_commands.Group(name="hd2", description="Commands for Helldivers 2.")

    @pc.command(name="war", description="get war state.")
    async def warstat(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apidata.get("war", None)
        if not data:
            return await ctx.send("No result")
        print(data)
        await ctx.send(embed=create_war_embed(data))

    @pc.command(name="assign", description="get assignment state.")
    async def assignstate(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apidata.get("assignments", None)
        if not data:
            return await ctx.send("No result")
        await ctx.send(embed=create_assignment_embed(data[0]))

    @pc.command(name="campaigns", description="get campaign state.")
    async def cstate(self, interaction: discord.Interaction,filter:Literal[0,2,3]=0,byplanet:int=0):
        ctx: commands.Context = await self.bot.get_context(interaction)

        data = self.apidata.get("campaigns", None)
        if not data:
            return await ctx.send("No result")
        for camp in data:
            if "planet" in camp:
                if byplanet!=0:
                    if camp['planet']['index']==byplanet:
                        
                        cstr = create_campaign_str(camp)
                        await ctx.send(embed=create_planet_embed(camp["planet"], cstr=cstr))
                else:
                    if filter==0:
                        cstr = create_campaign_str(camp)
                        await ctx.send(embed=create_planet_embed(camp["planet"], cstr=cstr))
                    elif filter==2:
                        evtcheck=camp['planet']['event']
                        if evtcheck:
                            evtcheck=evtcheck['faction']=='Terminids'
                        if camp['planet']['currentOwner']=='Terminids' or evtcheck:
                            cstr = create_campaign_str(camp)
                            await ctx.send(embed=create_planet_embed(camp["planet"], cstr=cstr))
                    elif filter==3:
                        evtcheck=camp['planet']['event']
                        if evtcheck:
                            evtcheck=evtcheck['faction']=='Automaton'
                        if camp['planet']['currentOwner']=='Automaton' or evtcheck:
                            cstr = create_campaign_str(camp)
                            await ctx.send(embed=create_planet_embed(camp["planet"], cstr=cstr))


async def setup(bot):
    await bot.add_cog(HelldiversCog(bot))


async def teardown(bot):
    await bot.remove_cog("HelldiversCog")
