import asyncio
import json
import datetime
import difflib
from typing import Any, Dict, List, Optional, Tuple, Union

import discord
from dateutil.rrule import MINUTELY, rrule
from discord.ext import commands, tasks
import os
import cogs.HD2 as hd2
from cogs.HD2.GameStatus import ApiStatus
from cogs.HD2.db import ServerHDProfile
from hd2api.models.ABC.model import BaseApiModel
from assetloader import AssetLookup

# import datetime
from bot import (
    TC_Cog_Mixin,
    TCBot,
)
from hd2api import hdml_parse, GetApiDirectSpaceStation

import gui
from utility import WebhookMessageWrapper as web
from bot.Tasks import TCTask, TCTaskManager


from pydantic import Field
from discord.utils import format_dt as fdt


from hd2api.builders import get_time_dh
from hd2api import (
    DiveharderAll,
    NewsFeedItem,
    PlanetStatus,
    GlobalResource,
    PlanetInfo,
    PlanetEvent,
    Campaign,
    SpaceStationStatus,
    Planet,
    GlobalEvent,
    SectorStates,
    PlanetAttack,
    PlanetActiveEffects,
    KnownPlanetEffect,
    build_planet_effect,
    build_all_regions,
)
from hd2api.models import PlanetRegion, PlanetRegionInfo

from hd2api.constants import faction_names, region_size_enums
from cogs.HD2.maths import maths
from cogs.HD2.diff_util import process_planet_attacks, GameEvent, EventModes
from utility.manual_load import load_json_with_substitutions


class SimplePlanet(BaseApiModel):
    index: Optional[int] = Field(alias="index", default=None)

    name: Optional[Union[str, Dict[str, Any]]] = Field(alias="name", default=None)

    owner: Optional[int] = Field(alias="owner", default=0)

    sector: Optional[str] = Field(alias="sector", default=None)

    waypoints: Optional[List[int]] = Field(alias="waypoints", default=None)

    regenPerSecond: Optional[float] = Field(alias="regenPerSecond", default=None)

    def get_name(self, faction=True) -> str:
        """Get the name of the planet, along with occupying faction
        and planet index."""
        if not faction:
            return f"P#{self.index}: {self.name}"
        return f"P#{self.index}: {self.name}"

    @classmethod
    def from_planet_status(cls, planet_status: PlanetStatus):
        data_path: str = "./hd2json/planets/planets.json"

        with open(data_path, "r") as file:
            planets_data_json = json.load(file)

        pval = planets_data_json.get(str(planet_status.index), None)
        name = sector = "NA"
        if pval:
            name = pval["name"]
            sector = pval["sector"]

        return cls(
            index=int(planet_status.index),
            name=name,
            owner=planet_status.owner,
            sector=sector,
            waypoints=[],
            regenPerSecond=planet_status.regenPerSecond,
        )

    @classmethod
    def from_index(cls, index: int):
        data_path: str = "./hd2json/planets/planets.json"

        with open(data_path, "r") as file:
            planets_data_json = json.load(file)

        pval = planets_data_json.get(str(index), None)
        name = sector = "NA"
        if pval:
            name = pval["name"]
            sector = pval["sector"]

        return cls(
            index=int(index),
            name=name,
            owner=0,
            sector=sector,
            waypoints=[],
            regenPerSecond=0.0,
        )


class Events:
    """Class for event combination grouping."""

    def __init__(self) -> None:
        self.planet = None
        self.lastInfo: Dict[str, Any] = {}
        self.lastStatus: Dict[str, Any] = {}
        self.evt: List[GameEvent] = []
        self.trig: List[str] = []
        self.ret = None

    def add_event(self, event: GameEvent, key: str) -> None:
        self.evt.append(event)
        if event.mode in [EventModes.NEW, EventModes.REMOVE]:
            self.ret = event.value.retrieved_at
        elif event.mode == EventModes.CHANGE:
            self.ret = event.value[0].retrieved_at

        if key not in self.trig:
            self.trig.append(key)


class PlanetEvents(Events):
    def __init__(self, planet: Planet) -> None:
        super().__init__()
        self.planet: Planet = planet
        self.planet_event: Optional[str] = None
        self.planet1: Optional[str] = None

    def invasion_check(self):
        if self.planet_event:
            if self.planet_event.eventType == 2:
                return True
        return False

    def get_links(self) -> Tuple[List[int], List[int]]:
        new, old = [], []
        if "waypoints" in self.lastInfo:
            for i, v in self.lastInfo["waypoints"].items():
                for t, ind in v.items():
                    if t == "new":
                        new.append(ind)
                    if t == "old":
                        old.append(ind)

        common = [elem for elem in new if elem in old]

        for c in common:
            if c in new:
                new.remove(c)
            if c in old:
                old.remove(c)

        return new, old

    def get_last_planet_owner(self) -> Tuple[int, int]:
        new, old = self.planet.owner, self.planet.owner
        if "owner" in self.lastStatus:
            if "old" in self.lastStatus["owner"]:
                old = self.lastStatus["owner"]["old"]
            if "new" in self.lastStatus["owner"]:
                new = self.lastStatus["owner"]["new"]
        return new, old

    def update_planet(
        self, value: Tuple[SimplePlanet, Dict[str, Any]], place: str
    ) -> None:
        v, _ = value
        if place == "planets":
            self.lastStatus = _
            self.planet.owner = v.owner
            self.planet.regenPerSecond = v.regenPerSecond
            self.ret = v.retrieved_at
        elif place == "planetInfo":
            self.lastInfo = _
            self.planet.waypoints = v.waypoints
            self.ret = v.retrieved_at


class SectorEvents(Events):
    def __init__(self, planet: SectorStates) -> None:
        super().__init__()
        self.planet: SectorStates = planet
        self.planet_event = None


class GeneralEvents(Events):
    def __init__(self) -> None:
        super().__init__()
        self.planet = None
        self.hdml = ""


faction_dict = {1: "Human", 2: "Terminid", 3: "Automaton", 4: "Illuminate"}


class Batch:
    def __init__(self, batch_id: str) -> None:
        self.batch_id: str = batch_id
        self.time: datetime.datetime = datetime.datetime.now()
        self.planets: Dict[str, PlanetEvents] = {}
        self.hd2: Dict[str, Any] = load_json_with_substitutions(
            "./assets/json", "logreasons.json", {}
        )
        self.general: GeneralEvents = GeneralEvents()
        self.sector: Dict[str, SectorEvents] = {}

    def add_event(
        self,
        event: GameEvent,
        planet_name: Optional[str],
        key: str,
        planet: Optional[Planet],
        sector_name: Optional[str],
    ) -> None:
        gui.gprint(key)
        if sector_name is not None:
            if sector_name not in self.sector:
                self.sector[sector_name] = SectorEvents(planet)
            self.sector[sector_name].add_event(event, key)
        elif planet_name is not None:
            if planet_name not in self.planets:
                self.planets[planet_name] = PlanetEvents(planet)
            self.planets[planet_name].add_event(event, key)
        else:
            self.general.add_event(event, key)

    def update_planet(
        self, planet_name: str, value: Tuple[Any, Dict[str, Any]], place: str
    ) -> None:
        if planet_name in self.planets:
            self.planets[planet_name].update_planet(value, place)

    def process_event(self, event: GameEvent, apistatus: Any) -> None:
        mode: EventModes = event.mode
        place: str = event.place
        value: Any = event.value
        planet_name_source: Optional[str] = None
        sector_name: Optional[str] = None
        planet: Optional[Planet] = None

        key: str = f"{place}_{mode}"

        if place in ["campaign", "planetevents"]:
            va = value
            if mode == EventModes.CHANGE:
                va, _ = value
            planet = SimplePlanet.from_index(va.planetIndex)
            # planet = apistatus.planets.get(int(value.planetIndex), None)
            if planet:
                planet_name_source = planet.get_name(False)

        if place in ["planets", "planetInfo"]:
            va = value
            if mode == EventModes.CHANGE:
                va, _ = value
            # planet = apistatus.planets.get(int(va.index), None)
            planet = SimplePlanet.from_index(va.index)
            if planet:
                planet_name_source = planet.get_name(False)

        if place in ["regions"]:
            va = value
            if mode == EventModes.CHANGE:
                va, _ = value
            # planet = apistatus.planets.get(int(va.index), None)

            planet = SimplePlanet.from_index(va.planetIndex)
            if planet:
                planet_name_source = planet.get_name(False)

        if place in ["sectors"]:
            va = value
            if mode == EventModes.CHANGE:
                va, _ = value
            planet = va
            if planet:
                sector_name = va.name

        if place in ["station"]:
            va = value
            if mode == EventModes.CHANGE:
                va, _ = value
            if va.planetIndex:
                planet = SimplePlanet.from_index(va.planetIndex)
                # planet = apistatus.planets.get(int(value.planetIndex), None)
                if planet:
                    planet_name_source = planet.get_name(False)
        if place in ["news"]:
            pass
        if place in ["planetAttacks"]:
            pass

        self.add_event(event, planet_name_source, key, planet, sector_name)

        if mode == EventModes.CHANGE and place != "sectors":
            self.update_planet(planet_name_source, value, place)
        if mode == EventModes.CHANGE and place == "sectors":
            pass

    async def format_combo_text(
        self, ctype: str, planet_data: PlanetEvents, ctext: List[List[str]], alls=None
    ) -> List[str]:
        targets: List[str] = []
        data_path: str = "./hd2json/planets/planets.json"

        with open(data_path, "r") as file:
            planets_data_json = json.load(file)

        if ctype in ["newlink", "destroylink"]:
            new, old = planet_data.get_links()
            links = new if ctype == "newlink" else old
            for i in links:
                target = (
                    ctext[1][0]
                    .replace("[TYPETEXT]", ctext[2][0])
                    .replace("[PLANET 0]", planet_data.planet.name)
                )
                target_name=f"P#{i}"
                if str(i) in planets_data_json:
                    target_name=planets_data_json[str(i)]["name"]
                target = target.replace("[PLANET 1]", target_name)
                target = target.replace("[SECTOR 1]", planet_data.planet.sector)
                target = target.replace(
                    "[FACTION]",
                    faction_dict.get(planet_data.planet.owner, "UNKNOWN")
                    + str(planet_data.planet.owner),
                )
                target += f" ({custom_strftime(planet_data.ret)})"
                targets.append(target)

        elif "region" in ctype:
            for evt in planet_data.evt:
                if evt.mode == EventModes.CHANGE and evt.place == "regions":
                    (info, dump) = evt.value
                    ym = "region_siege_changehands"
                    if "isAvailable" in dump:
                        if info.isAvailable:
                            ym = "region_siege_start"
                        elif not info.isAvailable and "owner" not in dump:
                            ym = "region_siege_end"
                        elif "owner" in dump:
                            ym = "region_siege_changehands"
                    elif "owner" in dump:
                        ym = "region_siege_changehands"
                    ctext = alls[ym]
                    target = (
                        ctext[1][0]
                        .replace("[TYPETEXT]", ctext[2][0])
                        .replace("[PLANET 0]", planet_data.planet.name)
                    )
                    target = target.replace("[SECTOR 1]", planet_data.planet.sector)

                    target += f" ({custom_strftime(planet_data.ret)})"
                    if ctype == "region_siege_start":
                        target = target.replace(
                            "[FACTION]", faction_dict.get(1, "UNKNOWN")
                        )
                    else:
                        if info.owner is not None:
                            target = target.replace(
                                "[FACTION]",
                                faction_dict.get(info.owner, "UNKNOWN"),
                            )
                        else:
                            target = target.replace(
                                "[FACTION]",
                                faction_dict.get(planet_data.planet.owner, "UNKNOWN"),
                            )
                    target = target.replace("[RegionIndex]", str(info.regionIndex))
                    target = target.replace("[RegionName]", str(info.name))
                    target = target.replace(
                        "[RegionSize]",
                        region_size_enums.get(info.regionSize, "UnknownSize"),
                    )

                    targets.append(target)

        elif planet_data.planet is not None:
            target = (
                ctext[1][0]
                .replace("[TYPETEXT]", ctext[2][0])
                .replace("[PLANET 0]", planet_data.planet.name)
            )
            target = target.replace("[SECTOR 1]", planet_data.planet.sector)
            if (
                ctype == "defense start" or ctype == "invasion start"
            ) and planet_data.planet_event:
                target = target.replace(
                    "[FACTION]",
                    faction_dict.get(planet_data.planet_event.race, "UNKNOWN"),
                )
            else:
                target = target.replace(
                    "[FACTION]", faction_dict.get(planet_data.planet.owner, "UNKNOWN")
                )
            target += f" ({custom_strftime(planet_data.ret)})"
            if "DSS_EFFECT" in target:
                for evt in planet_data.evt:
                    if evt.mode == EventModes.CHANGE and evt.place == "station":
                        (info, dump) = evt.value
                        if "activeEffectIds" in dump:
                            gui.gprint(dump)
                            # combinations.append("dss effect")
                            target = await self.format_dss(target, info.id32)

            targets.append(target)
        else:
            out = ctext[1][0]
            target = ctext[1][0].replace("[TYPETEXT]", ctext[2][0])
            if "HDML" in target:
                target = target.replace("[HDML]", planet_data.hdml)
            target += f" ({custom_strftime(planet_data.ret)})"
            targets.append(target)
        return targets

    async def format_dss(self, t: str, id=749875195):
        station = await GetApiDirectSpaceStation(id)
        mode = "ends"
        effect = "()"
        endeffect = ""
        endsec = 0
        for tact in station.tacticalActions:
            if tact.status == 2:
                effect = tact.name or "UNKNOWN"
                mode = "starts"
            elif tact.status == 3:
                if tact.statusExpireAtWarTimeSeconds > endsec:
                    endsec = tact.statusExpireAtWarTimeSeconds
                endeffect = tact.name or "UNKNOWN"
        if mode == "starts":
            t = t.replace("[DSS_EFFECT]", effect)
        elif mode == "ends":
            t = t.replace("[DSS_EFFECT]", endeffect)

        t = t.replace("[DSS_EFFECT_MODE]", mode)
        return t

    def format_combo_text_generic(
        self, ctype: str, planet_data: GeneralEvents, ctext: List[List[str]]
    ) -> List[str]:
        targets: List[str] = []

        target = (
            ctext[1][0]
            .replace("[TYPETEXT]", ctext[2][0])
            .replace("[PLANET 0]", planet_data.planet.name)
        )
        target = target.replace("[SECTOR 1]", planet_data.planet.sector)
        if ctype == "defense start" and planet_data.planet_event:
            target = target.replace(
                "[FACTION]",
                faction_dict.get(planet_data.planet_event.race, "UNKNOWN"),
            )
        else:
            target = target.replace(
                "[FACTION]", faction_dict.get(planet_data.planet.owner, "UNKNOWN")
            )
        target += f" ({custom_strftime(planet_data.ret)})"
        targets.append(target)
        return targets

    async def combo_checker(self) -> List[str]:
        """Check for event combos"""
        combos: List[str] = []

        for planet_data in self.planets.values():
            # Start checking all planet events.
            trigger_list: List[str] = planet_data.trig

            gui.gprint(trigger_list)
            combo: List[str] = self.check_planet_trigger_combinations(
                trigger_list, planet_data
            )
            if combo:
                for c in combo:
                    if c in self.hd2:
                        text: List[str] = await self.format_combo_text(
                            c, planet_data, self.hd2[c], self.hd2
                        )
                        combos.extend(text)
                    else:
                        combos.append(str(c))

        for sector_data in self.sector.values():
            trigger_list: List[str] = sector_data.trig
            combos.append(str(sector_data.planet.name) + ":" + ",".join(trigger_list))

            combo: List[str] = self.check_sector_trig_combinations(
                trigger_list, sector_data
            )
            if combo:
                for c in combo:
                    if c in self.hd2:
                        text: List[str] = await self.format_combo_text(
                            c, sector_data, self.hd2[c]
                        )
                        combos.extend(text)
                    else:
                        combos.append(str(c))

        if self.general.evt:
            general = self.general
            trig = general.trig
            combo: List[str] = self.check_generic_trig_combinations(trig, general)
            if combo:
                for c in combo:
                    if c in self.hd2:
                        text: List[str] = await self.format_combo_text(
                            c, general, self.hd2[c]
                        )
                        combos.extend(text)
                    else:
                        combos.append(str(c))

        return combos

    def contains_all_values(
        self, input_list: List[str], target_list: List[str]
    ) -> bool:
        for value in target_list:
            if value not in input_list:
                return False
        return True

    def check_planet_trigger_combinations(
        self, trigger_list: List[str], planet_data: PlanetEvents
    ) -> List[str]:
        """Get a list of valid "combos", game events that happen when certain status elements
        are added/removed/changed at the same time."""
        planet: Planet = planet_data.planet
        combinations: List[str] = []

        if "station_EventModes.CHANGE" in trigger_list:
            for evt in planet_data.evt:
                if evt.mode == EventModes.CHANGE and evt.place == "station":
                    (info, dump) = evt.value
                    if "planetIndex" in dump:
                        combinations.append("station move")
                    elif "activeEffectIds" in dump:
                        gui.gprint(dump)
                        combinations.append("dss effect")

        if "regions_EventModes.CHANGE" in trigger_list:
            for evt in planet_data.evt:
                gui.gprint(evt.mode, evt.place, evt.value)
                if evt.mode == EventModes.CHANGE and evt.place == "regions":
                    (info, dump) = evt.value
                    if "region" not in combinations:
                        # many regions per planet.
                        combinations.append("region")

                        gui.gprint(combinations, evt.mode, evt.place, evt.value)

        if (
            "campaign_EventModes.NEW" in trigger_list
            and "planetevents_EventModes.NEW" not in trigger_list
        ):
            combinations.append("cstart")

        if self.contains_all_values(
            trigger_list, ["campaign_EventModes.NEW", "planetevents_EventModes.NEW"]
        ):
            if planet_data.invasion_check():
                combinations.append("invasion start")
            else:
                combinations.append("defense start")

        if (
            "campaign_EventModes.REMOVE" in trigger_list
            and "planetevents_EventModes.REMOVE" not in trigger_list
        ):
            combinations.append("cend")

        if self.contains_all_values(
            trigger_list, ["campaign_EventModes.REMOVE", "planets_EventModes.CHANGE"]
        ):
            if planet and planet.owner == 1:
                new, old = planet_data.get_last_planet_owner()
                if old != new:
                    combinations.append("planet won")

        if self.contains_all_values(
            trigger_list,
            [
                "campaign_EventModes.REMOVE",
                "planetevents_EventModes.REMOVE",
                "planets_EventModes.CHANGE",
            ],
        ):
            if planet and planet.owner != 1:
                combinations.append("defense lost")

        if (
            self.contains_all_values(
                trigger_list,
                ["campaign_EventModes.REMOVE", "planetevents_EventModes.REMOVE"],
            )
            and "planets_EventModes.CHANGE" not in trigger_list
        ):
            if planet_data.invasion_check():
                if (
                    planet_data.planet_event.health / planet_data.planet_event.maxHealth
                ) <= 0.05:
                    combinations.append("invasion won")
                else:
                    combinations.append("invasion lost")
            else:
                combinations.append("defense won")

        if self.contains_all_values(
            trigger_list,
            [
                "campaign_EventModes.REMOVE",
                "planetevents_EventModes.REMOVE",
                "planets_EventModes.CHANGE",
            ],
        ):
            if planet and planet.owner == 1:
                combinations.append("defense won")

        if (
            "planets_EventModes.CHANGE" in trigger_list
            and "campaign_EventModes.REMOVE" not in trigger_list
        ):
            if planet and planet.owner != 1:
                new, old = planet_data.get_last_planet_owner()
                if old != new:
                    combinations.append("planet flip")

        if "planets_EventModes.CHANGE" in trigger_list:
            pass
            # combinations.append("pcheck")

        if any(
            value in trigger_list for value in ["planetInfo_EventModes.CHANGE"]
        ) and self.is_anew_link(planet, planet_data):
            combinations.append("newlink")

        if any(
            value in trigger_list for value in ["planetInfo_EventModes.CHANGE"]
        ) and self.is_destroyed_link(planet, planet_data):
            combinations.append("destroylink")

        return combinations if combinations else []

    def check_sector_trig_combinations(
        self, trigger_list: List[str], planet_data: SectorEvents
    ) -> List[str]:
        combinations: List[str] = []
        if "sectors_EventModes.CHANGE" in trigger_list:
            combinations.append("sector_state")

        return combinations if combinations else []

    def check_generic_trig_combinations(
        self, trigger_list: List[str], general: GeneralEvents
    ) -> Optional[List[str]]:
        combinations: List[str] = []
        if "news_EventModes.NEW" in trigger_list:
            combinations.append("dispatch new")

        return combinations if combinations else None

    def is_anew_link(self, planet: Planet, target_planet: PlanetEvents) -> bool:
        if target_planet:
            new, old = target_planet.get_links()
            if new:
                return True
        return False

    def is_destroyed_link(self, planet: Planet, target_planet: PlanetEvents) -> bool:
        if target_planet:
            new, old = target_planet.get_links()
            if old:
                return True
        return False


def check_platform():
    if os.name == "nt":
        return "%#I:%M%p UTC {S} %b %Y"
    return "%-I:%M%p UTC {S} %b %Y"


def suffix(d):
    return {1: "st", 2: "nd", 3: "rd"}.get(d % 20, "th")


def custom_strftime(t):
    format = "%#I:%M%p UTC {S} %b %Y"
    out = t.strftime(format).replace("{S}", str(t.day) + suffix(t.day))
    out = out.replace("AM", "am")
    out = out.replace("PM", "pm")
    return out


def getColor(owner):
    if owner == 2:
        return 0xEF8E20
    elif owner == 3:
        return 0xEF2020
    elif owner == 1:
        return 0x79E0FF
    return 0x960096


colors = {
    "automaton": 0xFE6D72,  # Red
    "terminids": 0xFFC100,  # Yellow
    "humans": 0x009696,  # Cyan-like color
    "illuminate": 0x960096,
}

colors2 = {
    "automaton": 0xEF2020,  # Red
    "terminids": 0xEF8E20,  # Yellow
    "humans": 0x79E0FF,  # Cyan-like color
    "illuminate": 0x960096,
}

inds2 = {
    "automaton": 3,  # Red
    "terminids": 2,  # Yellow
    "humans": 1,  # Cyan-like color
    "illuminate": 4,
}


class Embeds:
    @staticmethod
    def campaignLogEmbed(
        campaign: Campaign, planet: Optional[Planet], mode="started"
    ) -> discord.Embed:
        strc = hd2.embeds.create_campaign_str(campaign)
        name, sector = campaign.planetIndex, None
        color = 0x009696
        if planet:
            name, sector = planet.get_name(False), planet.sector
            color = colors.get(planet.currentOwner.lower(), 0x009696)

        emb = discord.Embed(
            title=f"{name} Campaign {mode}",
            description=f"A campaign has {mode} for **{name}**, in sector **{sector}**.\n{strc}\nTimestamp:{fdt(campaign.retrieved_at, 'F')}",
            timestamp=campaign.retrieved_at,
            color=color,
        )
        emb.set_author(name=f"Campaign {mode}.")
        emb.set_footer(text=f"{strc},{custom_strftime(campaign.retrieved_at)}")
        return emb

    @staticmethod
    def campaignsLogEmbed(
        campaign: Campaign, planet: Optional[Planet], mode="started"
    ) -> discord.Embed:
        strc = hd2.embeds.create_campaign_str(campaign)
        name, sector = campaign.planetIndex, None
        color = 0x009696
        if planet:
            name, sector = planet.get_name(False), planet.sector
            color = colors.get(planet.currentOwner.lower(), 0x009696)

        emb = discord.Embed(
            title=f"{name} Campaign {mode}",
            description=f"A campaign has {mode} for {name}, in sector {sector}.\n{strc}\nTimestamp:{fdt(campaign.retrieved_at, 'F')}",
            timestamp=campaign.retrieved_at,
            color=color,
        )
        emb.set_author(name=f"Campaign {mode}.")
        emb.set_footer(text=f"{strc},{custom_strftime(campaign.retrieved_at)}")
        return emb

    @staticmethod
    def deadzoneWarningEmbed(campaign: BaseApiModel, mode="started") -> discord.Embed:
        emb = discord.Embed(
            title="DEADZONE DETECTED",
            description=f"A likely deadzone was {mode}!\nTimestamp:{fdt(campaign.retrieved_at, 'F')}",
            timestamp=campaign.retrieved_at,
            color=0xFF0000,
        )
        emb.set_author(name="DEADZONE WARNING.")
        emb.set_footer(text=f"{custom_strftime(campaign.retrieved_at)}")
        return emb

    @staticmethod
    def timetravelWarningEmbed(campaign: BaseApiModel, mode="started") -> discord.Embed:
        emb = discord.Embed(
            title="TIME TRAVEL DETECTED",
            description=f"The returned internal war time has rolled back to a state about 10 seconds prior. \nThe war is paused until arrowhead gets this fixed.\nTimestamp:{fdt(campaign.retrieved_at, 'F')}",
            timestamp=campaign.retrieved_at,
            color=0xFF0000,
        )
        emb.set_author(name="TIME TRAVEL WARNING.")
        emb.set_footer(text=f"{custom_strftime(campaign.retrieved_at)}")
        return emb

    @staticmethod
    def planetAttackEmbed(
        atk: PlanetAttack, planets: Dict[int, Planet], mode="started"
    ):
        source = planets.get(atk.source, None)
        target = planets.get(atk.target, None)
        source_name = atk.source
        target_name = atk.target
        if source:
            source_name = source.get_name(False)
        if target:
            target_name = target.get_name(False)
        emb = discord.Embed(
            title=f"Planet Attack {mode}",
            description=f"An attack has {mode} from {source_name} to {target_name}.   \nTimestamp:{fdt(atk.retrieved_at, 'F')}",
            timestamp=atk.retrieved_at,
            color=0x707CC8 if mode == "started" else 0xC08888,
        )
        emb.set_author(name=f"Planet Attack {mode}.")
        emb.set_footer(text=f"{custom_strftime(atk.retrieved_at)}")
        return emb

    @staticmethod
    def planetAttacksEmbed(
        atks: List[GameEvent], planets: Dict[int, Planet], mode="started"
    ):
        strings = []
        if mode == EventModes.ADDED:
            mode = "added"
        elif mode == EventModes.REMOVED:
            mode = "removed"

        timestamp = discord.utils.utcnow()
        for atkv in atks.value:
            atk = atkv.value
            source = planets.get(atk.source, None)
            target = planets.get(atk.target, None)
            source_name = atk.source
            target_name = atk.target
            if source:
                source_name = source.get_name(False)
            if target:
                target_name = target.get_name(False)
            string = f"Attack {mode}: {source_name} to {target_name}."
            strings.append(string)
            timestamp = atk.retrieved_at
        emb = discord.Embed(
            title="Planet Attacks",
            description="\n".join([f"* {s}" for s in strings]),
            timestamp=timestamp,
            color=0x707CC8 if mode == EventModes.ADDED else 0xC08888,
        )
        emb.set_author(name=f"Planet Attack {mode}.")
        emb.set_footer(text=f"{custom_strftime(timestamp)}")
        return emb

    @staticmethod
    def planeteventsEmbed(
        campaign: PlanetEvent, planet: Optional[Planet], mode="started"
    ) -> discord.Embed:
        name, sector = campaign.planetIndex, None
        color = 0x009696
        if planet:
            name, sector = planet.get_name(False), planet.sector
        emb = discord.Embed(
            title=f"Planet {name} Event {mode}",
            description=f"A new event has {mode} for {name}, in sector {sector}.   \nTimestamp:{fdt(campaign.retrieved_at, 'F')}",
            timestamp=campaign.retrieved_at,
            color=color,
        )
        emb.add_field(name="Event Details", value=campaign.long_event_details())
        emb.set_author(name=f"Planet Event {mode}.")
        emb.set_footer(
            text=f"EID:{campaign.id}, {custom_strftime(campaign.retrieved_at)}"
        )
        return emb

    @staticmethod
    def planeteffectsEmbed(
        campaign: PlanetActiveEffects,
        planet: Optional[Planet],
        effectid: Optional[KnownPlanetEffect],
        mode="started",
    ) -> discord.Embed:
        name, sector = campaign.index, None
        color = 0x009696
        if planet:
            name, sector = planet.get_name(False), planet.sector
            color = colors2.get(planet.currentOwner.lower(), 0x009696)
        emb = discord.Embed(
            title=f"Planet {name} Effect {mode}",
            description=f"An Effect was {mode} for {name}, in sector {sector}.\n\n Timestamp:{fdt(campaign.retrieved_at, 'F')}",
            timestamp=campaign.retrieved_at,
            color=color,
        )

        emb.add_field(name="Galactic Effect ID", value=f"{campaign.galacticEffectId}")
        if effectid:
            emb.add_field(
                name=f"{effectid.name}", value=f"{effectid.description[:100]}"
            )
        emb.set_author(name=f"Planet Effect {mode}.")
        emb.set_footer(text=f"{custom_strftime(campaign.retrieved_at)}")
        return emb

    @staticmethod
    def globalEventEmbed(
        evt: GlobalEvent, mode="started", footerchanges=""
    ) -> discord.Embed:
        globtex = ""
        title = ""
        if evt.title:
            mes = hdml_parse(evt.title)
            globtex += f"### {mes}\n"
        if evt.message:
            mes = hdml_parse(evt.message)
            globtex += f"{mes}\n\n"
        emb = discord.Embed(
            title=f"Global Event {mode}",
            description=f"A global event has {mode}.\n{globtex}",
            timestamp=evt.retrieved_at,
            color=0x709C68,
        )
        emb.add_field(name="Event Details", value=evt.strout())
        emb.add_field(name="Timestamp", value=f"Timestamp:{fdt(evt.retrieved_at, 'F')}")
        emb.set_author(name=f"Global Event {mode}.")
        emb.set_footer(
            text=f"{footerchanges},EID:{evt.eventId}, {custom_strftime(evt.retrieved_at)}"
        )
        return emb

    @staticmethod
    def resourceEmbed(
        evt: GlobalResource, mode="started", footerchanges=""
    ) -> discord.Embed:
        emb = discord.Embed(
            title=f"Global Resource {mode}",
            description=f"A global Resource was {mode}.\n It's id32 is **{evt.id32}**\n `{evt.currentValue}/{evt.maxValue}`",
            timestamp=evt.retrieved_at,
            color=0xAC50FE,
        )

        emb.add_field(name="Timestamp", value=f"Timestamp:{fdt(evt.retrieved_at, 'F')}")
        emb.set_author(name=f"Global Resource {mode}.")
        emb.set_footer(
            text=f"{footerchanges},RID:{evt.id32}, {custom_strftime(evt.retrieved_at)},flags={evt.flags}"
        )
        return emb

    @staticmethod
    def spaceStationEmbed(
        evt: SpaceStationStatus, dump: Dict[str, Any], status: ApiStatus, mode="started"
    ) -> discord.Embed:
        name, sector = "Space Station", None
        specialtext = ""
        color = 0x02A370
        emb = discord.Embed(
            title=f"{name} Field Change",
            description=f"Updates for Space Station {evt.id32}.\n",
            timestamp=evt.retrieved_at,
            color=color,
        )

        if "currentElectionEndWarTime" in dump:
            start = get_time_dh(status.warall)
            exp = start + datetime.timedelta(seconds=evt.currentElectionEndWarTime)
            emb.add_field(name="New Election Period End Time", value=fdt(exp, "F"))
        if "planetIndex" in dump:
            planet = status.planets.get(evt.planetIndex)
            emb.add_field(name="Planet", value=planet.get_name())
        if "flags" in dump:
            emb.add_field(name="Flag", value=evt.flags)
        if "activeEffectIds" in dump:
            ids = f"`[{', '.join(map(str, evt.activeEffectIds))}]`"
            emb.add_field(name="Active Effect IDs", value=ids, inline=False)

        emb.add_field(name="Timestamp", value=f"Timestamp:{fdt(evt.retrieved_at, 'F')}")
        emb.set_author(name=f"Station {evt.id32}")
        emb.set_footer(text=f"{custom_strftime(evt.retrieved_at)}")
        return emb

    @staticmethod
    def RegionEmbed_PlanetRegion(
        campaign: "PlanetRegion",
        planet: Optional["Planet"] = None,
        mode: str = "started",
    ) -> discord.Embed:
        """
        Generate a Discord embed representing the state of a region on a planet from PlanetRegion data.
        """
        name = "Unknown Planet"
        sector = "Unknown Sector"
        color = 0x8C90B0
        specialtext = ""

        if planet:
            name = planet.get_name(False)
            sector = planet.sector or "N/A"
            color = colors2.get(planet.currentOwner.lower(), 0x8C90B0)

        embed = discord.Embed(
            title=f"{name} Region Report",
            description=f"Status **{mode}** for {name}, in sector {sector}.{specialtext}",
            timestamp=campaign.retrieved_at,
            color=color,
        )
        gui.gprint(campaign)

        field_map = {
            "Planet Index": campaign.planetIndex,
            "Region Index": campaign.regionIndex,
            "Owner Faction": campaign.owner,
            "Health": campaign.health,
            "Regen Rate": campaign.regenPerSecond,
            "Availability Factor": campaign.availabilityFactor,
            "Is Available": campaign.isAvailable,
            "Active Players": campaign.players,
        }

        for field_name, value in field_map.items():
            embed.add_field(name=field_name, value=str(value), inline=True)

        embed.add_field(
            name="Timestamp", value=f"Timestamp:{fdt(campaign.retrieved_at, 'F')}"
        )
        embed.set_author(name="Region Value Change")
        embed.set_footer(text=f"{custom_strftime(campaign.retrieved_at)}")

        return embed

    @staticmethod
    def RegionEmbed_PlanetRegionInfo(
        campaign: "PlanetRegionInfo",
        planet: Optional["Planet"] = None,
        mode: str = "started",
    ) -> discord.Embed:
        """
        Generate a Discord embed representing the info of a region on a planet from PlanetRegionInfo data.
        """
        name = "Unknown Planet"
        sector = "Unknown Sector"
        color = 0x8C90B0
        specialtext = ""

        if planet:
            name = planet.get_name(False)
            sector = planet.sector or "N/A"
            color = colors2.get(planet.currentOwner.lower(), 0x8C90B0)

        embed = discord.Embed(
            title=f"{name} Region Report",
            description=f"Status **{mode}** for {name}, in sector {sector}.{specialtext}",
            timestamp=campaign.retrieved_at,
            color=color,
        )
        gui.gprint(campaign)

        field_map = {
            "Planet Index": campaign.planetIndex,
            "Region Index": campaign.regionIndex,
            "Settings Hash": campaign.settingsHash,
            "Max Health": campaign.maxHealth,
            "Region Size": campaign.regionSize,
        }

        for field_name, value in field_map.items():
            embed.add_field(name=field_name, value=str(value), inline=True)

        embed.add_field(
            name="Timestamp", value=f"Timestamp:{fdt(campaign.retrieved_at, 'F')}"
        )
        embed.set_author(name="Region Info Report")
        embed.set_footer(text=f"{custom_strftime(campaign.retrieved_at)}")

        return embed

    @staticmethod
    def dumpEmbedRegion(
        campaign: Union["PlanetRegion", "PlanetRegionInfo"],
        dump: Dict[str, Any],
        planet: Optional["Planet"] = None,
        mode: str = "started",
    ) -> discord.Embed:
        """
        Generate a Discord embed summarizing differences in region data,
        with each changed field as its own embed field.
        """
        name = "Unknown Planet"
        sector = "Unknown Sector"
        color = 0x8C90B0
        specialtext = ""

        # Set name, sector, and color if planet data is provided
        if planet:
            name = planet.get_name(False)
            sector = planet.sector or "N/A"
            color = colors2.get(planet.currentOwner.lower(), 0x8C90B0)

        # Owner change color override
        if "owner" in dump:
            old_owner = dump["owner"].get("old", 5)
            new_owner = dump["owner"].get("new", 5)
            if old_owner is None:
                old_owner = inds2.get(planet.currentOwner.lower(), 0)
            if new_owner is None:
                new_owner = inds2.get(planet.currentOwner.lower(), 0)
            color = getColor(new_owner)
            specialtext += (
                f"\n* Owner: `{faction_names.get(old_owner, 'Unknown')}`"
                f" → `{faction_names.get(new_owner, 'Unknown')}`"
            )

        # Regen rate change description (LPH)
        if "regenPerSecond" in dump:
            old_rps = dump["regenPerSecond"].get("old", 0.0) or 0
            new_rps = dump["regenPerSecond"].get("new", 0.0) or 0
            if old_rps is None:
                old_rps = 0
            if new_rps is None:
                new_rps = 0
            old_lph = round(maths.dps_to_lph(old_rps), 3)
            new_lph = round(maths.dps_to_lph(new_rps), 3)
            specialtext += f"\n* Regen Rate: `{old_lph}` → `{new_lph}` LPH"
        rname = campaign.get("name", "None")
        rsize = campaign.get("regionSize", "UNKNOWNSIZE")
        embed = discord.Embed(
            title=f"Region {rname} in {name} Field Change",
            description=f"Stats **{mode}** for {name}'s {rname} (size  {rsize}), in sector {sector}.{specialtext}",
            timestamp=campaign.retrieved_at,
            color=color,
        )

        # Always show planet and region index if available
        planet_index = getattr(campaign, "planetIndex", "N/A")
        region_index = getattr(campaign, "regionIndex", "N/A")
        embed.add_field(name="Planet Index", value=str(planet_index), inline=True)
        embed.add_field(name="Region Index", value=str(region_index), inline=True)

        # Add each changed value as its own embed field
        for key, val in dump.items():
            if isinstance(val, dict) and "old" in val and "new" in val:
                old = val["old"]
                new = val["new"]

                embed.add_field(name=key, value=f"`{old}` → `{new}`", inline=True)
            else:
                embed.add_field(name=key, value=str(val), inline=True)

        embed.add_field(
            name="Timestamp", value=f"Timestamp:{fdt(campaign.retrieved_at, 'F')}"
        )
        embed.set_author(name="Region Value  Change")
        embed.set_footer(text=f"{custom_strftime(campaign.retrieved_at)}")

        return embed

    @staticmethod
    def dumpEmbedPlanet(
        campaign: Union[PlanetStatus, PlanetInfo],
        dump: Dict[str, Any],
        planet: Optional[Planet],
        mode="started",
    ) -> discord.Embed:
        name, sector = "PLANET", None
        specialtext = ""
        color = 0x8C90B0
        if planet:
            name, sector = planet.get_name(False), planet.sector
            color = colors2.get(planet.currentOwner.lower(), 0x8C90B0)
        globtex = json.dumps(dump, default=str)
        if "owner" in dump:
            color = getColor(campaign.owner)
            old_owner = dump["owner"].get("old", 5)
            new_owner = dump["owner"].get("new", 5)
            specialtext += f"\n* Owner: `{faction_names.get(old_owner, 'er')}`->`{faction_names.get(new_owner, 'er')}`"
        if "regenPerSecond" in dump:
            old_decay = dump["regenPerSecond"].get("old", 99999)
            new_decay = dump["regenPerSecond"].get("new", 99999)
            old_decay = round(maths.dps_to_lph(old_decay), 3)
            new_decay = round(maths.dps_to_lph(new_decay), 3)
            specialtext += f"\n* Regen Rate: `{old_decay}`->`{new_decay}`"
        if "position" in dump:
            new_posx = dump["position"].get("x", {"new": 0}).get("new", 0)
            new_posy = dump["position"].get("y", {"new": 0}).get("new", 0)
            specialtext += f"\n*`{name} moves to X {campaign.position.x} Y {campaign.position.y} ({custom_strftime(campaign.retrieved_at)}`)"

        emb = discord.Embed(
            title=f"{name} Field Change",
            description=f"Stats {mode} for {name}, in sector {sector}.\n{specialtext}\n```{globtex[:3500]}```",
            timestamp=campaign.retrieved_at,
            color=color,
        )
        emb.add_field(
            name="Timestamp", value=f"Timestamp:{fdt(campaign.retrieved_at, 'F')}"
        )
        emb.set_author(name="Planet Value Change")
        emb.set_footer(text=f"{custom_strftime(campaign.retrieved_at)}")
        return emb

    @staticmethod
    def dumpEmbed(
        campaign: BaseApiModel, dump: Dict[str, Any], name: str, mode="started"
    ) -> discord.Embed:
        globtex = json.dumps(dump, default=str)
        emb = discord.Embed(
            title="UNSEEN API Change",
            description=f"Field changed for {name}\n```{globtex[:4000]}```",
            timestamp=campaign.retrieved_at,
            color=0x000054,
        )
        emb.add_field(
            name="Timestamp", value=f"Timestamp:{fdt(campaign.retrieved_at, 'F')}"
        )
        emb.set_author(name="API Value Change")
        emb.set_footer(text=f"{custom_strftime(campaign.retrieved_at)}")
        return emb

    @staticmethod
    def NewsFeedEmbed(gamevent: GameEvent, mode="started") -> discord.Embed:
        newsfeed: NewsFeedItem = gamevent.value
        title, desc = newsfeed.to_str()
        emb = discord.Embed(
            title=f"{title}",
            description=desc,
            timestamp=newsfeed.retrieved_at,
            color=0x222222,
        )
        emb.add_field(
            name="Timestamp", value=f"Timestamp:{fdt(newsfeed.retrieved_at, 'F')}"
        )
        emb.set_author(
            name=f"{mode} dispatch from Super Earth at wartime {gamevent.game_time}"
        )
        emb.set_footer(text=f"{custom_strftime(newsfeed.retrieved_at)}")
        return emb


def update_retrieved_at(data, nowv):
    if isinstance(data, dict):
        for k, v in data.items():
            if k == "retrieved_at":
                data[k] = nowv
            else:
                update_retrieved_at(v, nowv)
    elif isinstance(data, list):
        for item in data:
            update_retrieved_at(item, nowv)


class HelldiversAutoLog(commands.Cog, TC_Cog_Mixin):
    def __init__(self, bot):
        self.bot: TCBot = bot
        self.loghook = []
        self.get_running = False
        self.event_log = []
        self.spot = 1
        self.batches: dict[int, Batch] = {}
        self.test_with = []
        self.titleids = {}
        self.messageids = {}
        self.last_move = {}
        self.redirect_hook = ""
        snap = hd2.load_from_json("./saveData/mt_pairs.json")
        if snap:
            for i, v in snap["titles"].items():
                self.titleids[int(i)] = v
            for i, v in snap["messages"].items():
                self.messageids[int(i)] = v

        self.lock = asyncio.Lock()
        self.load_test_files()
        nowd = datetime.datetime.now()
        st = datetime.datetime(
            nowd.year,
            nowd.month,
            nowd.day,
            nowd.hour,
            int(nowd.minute // 2) * 2,
        )
        # Rule for grabbing from api.
        robj2 = rrule(freq=MINUTELY, interval=1, dtstart=st)
        self.QueueAll: asyncio.Queue[List[GameEvent]] = asyncio.Queue()
        self.EventQueue = asyncio.Queue()
        self.PlanetQueue = asyncio.Queue()
        if not TCTaskManager.does_task_exist("UpdateLog"):
            self.tc_task2 = TCTask("UpdateLog", robj2, robj2.after(st))
            self.tc_task2.assign_wrapper(self.updatelog)
        self.process_game_events.start()

    def cog_unload(self):
        TCTaskManager.remove_task("UpdateLog")
        self.process_game_events.cancel()
        hold = {"titles": self.titleids, "messages": self.messageids}
        hd2.save_to_json(hold, "./saveData/mt_pairs.json")

    def load_test_files(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        if os.path.exists("./saveData/testwith"):
            for filename in os.listdir("./saveData/testwith"):
                filepath = os.path.join("./saveData/testwith", filename)
                if os.path.isfile(filepath):
                    with open(filepath, "r") as file:
                        file_contents = json.load(file)
                        now = now + datetime.timedelta(days=1)
                        update_retrieved_at(file_contents, now.isoformat())

                        add = DiveharderAll(**file_contents)

                        self.test_with.append(add)

    async def batch_events(self, events):
        """Stitch multiple events together into one."""

        for event in events:
            batch_id = event["batch"]
            if batch_id not in self.batches:
                self.batches[batch_id] = Batch(batch_id)
            self.batches[batch_id].process_event(event, self.apistatus)

        for batch_id in list(self.batches.keys()):
            texts = await self.batches[batch_id].combo_checker()
            for t in texts:
                for hook in list(self.loghook):
                    try:
                        await web.postMessageAsWebhookWithURL(
                            hook,
                            message_content=t[:1950],
                            display_username="SUPER EVENT",
                            avatar_url=self.bot.user.avatar.url,
                        )
                    except Exception as e:
                        await self.bot.send_error(e, "Webhook error")
                        if hook != AssetLookup.get_asset("loghook", "urls"):
                            self.loghook.remove(hook)
                            # ServerHDProfile.set_all_matching_webhook_to_none(hook)

            self.batches.pop(batch_id)

        return self.batches

    async def batch_events_2(self, events):
        async with self.lock:
            try:
                await self.batch_events(events)
            except Exception as ex:
                await self.bot.send_error(ex, "LOG ERROR", True)

    @tasks.loop(seconds=2)
    async def process_game_events(self):
        try:
            try:
                item = self.QueueAll.get_nowait()
                await self.send_event_list(item)
                await asyncio.sleep(0.02)
            except asyncio.QueueEmpty:
                pass
        except Exception as ex:
            await self.bot.send_error(ex, "LOG ERROR FOR POST", True)

    async def send_event_list(self, item_list: List[GameEvent]):
        embeds: List[discord.Embed] = []
        subthread: List[discord.Embed] = []

        for item in item_list:
            # Go through each game event, build embeds.
            embed = await self.build_embed(item)
            if embed:
                if embed.title == "ResourceChange":
                    subthread.append(embed)
                else:
                    embeds.append(embed)
                    if embed.color == 0xAC50FE:
                        subthread.append(embed)

        # Position's switch
        thishook = AssetLookup.get_asset("subhook", "urls")
        if thishook:
            # Redirection code.
            for s in subthread:
                try:
                    await web.postMessageAsWebhookWithURL(
                        thishook,
                        message_content="This is a redirect",
                        display_username="Super Earth Event Log",
                        avatar_url=self.bot.user.avatar.url,
                        embed=[s],
                    )
                except Exception as e:
                    await self.bot.send_error(e, "Webhook error")

        if not embeds:
            return

        val_batches = self.group_embeds(embeds)
        await self.send_embeds_through_webhook(val_batches)

    def group_embeds(self, embeds: List[discord.Embed]):
        """Group Embeds Together."""
        val_batches = []
        batch = []
        for e in embeds:
            val = json.dumps(e.to_dict())
            size = len(val)
            if (
                sum(len(json.dumps(b.to_dict())) for b in batch) + size > 6000
                or len(batch) >= 10
            ):
                val_batches.append(batch)
                batch = [e]
            else:
                batch.append(e)
        if batch:
            val_batches.append(batch)
        return val_batches

    async def send_embeds_through_webhook(self, batches: List[discord.Embed]):
        for embeds in batches:
            for hook in list(self.loghook):
                try:
                    await web.postMessageAsWebhookWithURL(
                        hook,
                        message_content="",
                        display_username="Super Earth Event Log",
                        avatar_url=self.bot.user.avatar.url,
                        embed=embeds,
                    )
                except Exception as e:
                    await self.bot.send_error(e, "Webhook error")
                    if hook != AssetLookup.get_asset("loghook", "urls"):
                        self.loghook.remove(hook)

    async def send_last_planet_positions(self):
        now = discord.utils.utcnow()
        embs = []
        for ind, lis in self.last_move.items():
            embs.append(Embeds.dumpEmbedPlanet(lis[1], lis[2], lis[0], "changed"))
        if not embs:
            return
        batches = self.group_embeds(embs)
        await self.send_embeds_through_webhook(batches)

    async def build_embed(self, item: GameEvent) -> Optional[discord.Embed]:
        """Build up an embed.

        Args:
            item (GameEvent): _description_

        Returns:
           formatted discord embed.
        """
        event_type = item.mode
        if event_type == EventModes.GROUP:
            # Schedule a grouping task.
            task = asyncio.create_task(self.batch_events_2(item["value"]))
            return None

        batch = item["batch"]
        place = item["place"]
        value = item["value"]
        embed = None
        if item["cluster"]:
            if place == "planetAttacks":
                embed = Embeds.planetAttacksEmbed(
                    item, self.apistatus.planets, item.mode
                )
                embed.set_author(
                    name=f"{embed._author['name']} at wt {item['game_time']}"
                )

                return embed
        if event_type == EventModes.DEADZONE:
            embed = Embeds.deadzoneWarningEmbed(
                value,
                "started",
            )
        if event_type == EventModes.TIME_TRAVEL:
            embed = Embeds.timetravelWarningEmbed(
                value,
                "started",
            )
        if event_type == EventModes.DEADZONE_END:
            embed = Embeds.deadzoneWarningEmbed(
                value,
                "ended",
            )
        if event_type == EventModes.NEW:
            if place == "campaign":
                embed = Embeds.campaignLogEmbed(
                    value,
                    self.apistatus.planets.get(int(value.planetIndex), None),
                    "started",
                )
            elif place == "planetAttacks":
                embed = Embeds.planetAttackEmbed(
                    value, self.apistatus.planets, "started"
                )
            elif place == "planetevents":
                embed = Embeds.planeteventsEmbed(
                    value,
                    self.apistatus.planets.get(int(value.planetIndex), None),
                    "started",
                )
            elif place == "planetEffects":
                embed = Embeds.planeteffectsEmbed(
                    value,
                    self.apistatus.planets.get(int(value.index), None),
                    build_planet_effect(
                        self.apistatus.statics.effectstatic, value.galacticEffectId
                    ),
                    "added",
                )
            elif place == "resources":
                embed = Embeds.resourceEmbed(
                    value,
                    "added",
                )
            elif place == "globalEvents":
                ti = value.titleId32
                mi = value.messageId32
                tc, mc = False, False
                if value.title and ti is not None:
                    if self.titleids.get(ti, None) != value.title:
                        self.titleids[ti] = value.title
                        tc = True
                if value.message and mi is not None:
                    if self.messageids.get(mi, None) != value.message:
                        self.messageids[mi] = value.message
                        mc = True
                embed = Embeds.globalEventEmbed(value, "started")
            elif place == "news":
                embed = Embeds.NewsFeedEmbed(item, "New")
            elif place == "planetregions":
                planet = self.apistatus.planets.get(int(value.planetIndex), None)
                embed = Embeds.RegionEmbed_PlanetRegion(
                    value, planet, f"added in {place}"
                )
            elif place == "regioninfo":
                planet = self.apistatus.planets.get(int(value.planetIndex), None)
                embed = Embeds.RegionEmbed_PlanetRegionInfo(
                    value, planet, f"added in {place}"
                )

        elif event_type == EventModes.REMOVE:
            if place == "campaign":
                embed = Embeds.campaignLogEmbed(
                    value,
                    self.apistatus.planets.get(int(value.planetIndex), None),
                    "ended",
                )
            elif place == "planetAttacks":
                embed = Embeds.planetAttackEmbed(value, self.apistatus.planets, "ended")
            elif place == "planetevents":
                embed = Embeds.planeteventsEmbed(
                    value,
                    self.apistatus.planets.get(int(value.planetIndex), None),
                    "ended",
                )
            elif place == "planetEffects":
                embed = Embeds.planeteffectsEmbed(
                    value,
                    self.apistatus.planets.get(int(value.index), None),
                    build_planet_effect(
                        self.apistatus.statics.effectstatic, value.galacticEffectId
                    ),
                    "removed",
                )
            elif place == "globalEvents":
                ti = value.titleId32
                mi = value.messageId32
                tc, mc = False, False
                if value.title and ti is not None:
                    if self.titleids.get(ti, None) != value.title:
                        self.titleids[ti] = value.title
                        tc = True
                if value.message and mi is not None:
                    if self.messageids.get(mi, None) != value.message:
                        self.messageids[mi] = value.message
                        mc = True
                embed = Embeds.globalEventEmbed(value, "ended")
            elif place == "news":
                embed = Embeds.NewsFeedEmbed(item, "Retired")
            elif place == "resources":
                embed = Embeds.resourceEmbed(
                    value,
                    "removed",
                )
            elif place == "planetregions":
                planet = self.apistatus.planets.get(int(value.planetIndex), None)
                embed = Embeds.RegionEmbed_PlanetRegion(
                    value, planet, f"removed in {place}"
                )
            elif place == "regioninfo":
                planet = self.apistatus.planets.get(int(value.planetIndex), None)
                embed = Embeds.RegionEmbed_PlanetRegionInfo(
                    value, planet, f"removed in {place}"
                )
        elif event_type == EventModes.CHANGE:
            print("IS_EventModes.CHANGE")
            (info, dump) = value
            if place == "planets" or place == "planetInfo":
                planet = self.apistatus.planets.get(int(info.index), None)
                if planet:
                    # planets- owner, regenRate
                    # Every 15 minutes
                    if "position" in dump and len(list(dump.keys())) == 1:
                        if int(info.index) not in self.last_move:
                            self.last_move[int(info.index)] = [planet, info, dump]
                            return Embeds.dumpEmbedPlanet(
                                info, dump, planet, f"changed in {place}"
                            )
                        elif (
                            info.retrieved_at
                            - self.last_move[int(info.index)][1].retrieved_at
                        ).total_seconds() > 3600:
                            self.last_move[int(info.index)] = [planet, info, dump]
                            return Embeds.dumpEmbedPlanet(
                                info, dump, planet, f"changed in {place}"
                            )
                        self.last_move[int(info.index)] = [planet, info, dump]
                        if info.retrieved_at.minute % 15 != 0:
                            return None
                        embed = Embeds.dumpEmbedPlanet(
                            info, dump, planet, f"changed in {place}"
                        )
                        if (
                            info.retrieved_at.hour % 2 == 0
                            or info.retrieved_at.minute != 0
                        ):
                            embed.title = "ResourceChange"
                    else:
                        embed = Embeds.dumpEmbedPlanet(
                            info, dump, planet, f"changed in {place}"
                        )
                else:
                    embed = Embeds.dumpEmbed(
                        info, dump, "planet", f"changed in {place}"
                    )
            # if place == "planetregions" or place == "regioninfo":
            #     planet = self.apistatus.planets.get(int(info.planetIndex), None)
            #     if planet:
            #         embed = Embeds.dumpEmbedRegion(
            #             info, dump, planet, f"changed in {place}"
            #         )
            #     else:
            #         embed = Embeds.dumpEmbedRegion(
            #             info, dump, planet, f"changed in {place}"
            #         )
            if place == "regions":
                planet = self.apistatus.planets.get(int(info.planetIndex), None)
                if planet:
                    embed = Embeds.dumpEmbedRegion(
                        info, dump, planet, f"changed in {place}"
                    )
                else:
                    embed = Embeds.dumpEmbedRegion(
                        info, dump, planet, f"changed in {place}"
                    )

            elif place == "stats_raw":
                embed = Embeds.dumpEmbed(info, dump, "stats", "changed")
            elif place == "info_raw":
                embed = Embeds.dumpEmbed(info, dump, "info", "changed")
            elif place == "station":
                if "currentElectionEndWarTime" in dump and len(dump) == 1:
                    return None
                embed = Embeds.spaceStationEmbed(info, dump, self.apistatus, "changed")
            elif place == "globalEvents":
                listv = [k for k in dump.keys()]
                ti = info.titleId32
                mi = info.messageId32
                tc, mc = False, 0
                footer_delta = ""
                if info.title:
                    stored = hdml_parse(self.titleids.get(ti, ""))
                    new = hdml_parse(info.title)
                    if stored != new:
                        self.titleids[ti] = info.title
                        tc = True
                if info.message:
                    stored = hdml_parse(self.messageids.get(mi, ""))
                    new = hdml_parse(info.message)
                    if stored != new:
                        diff = difflib.ndiff(stored.splitlines(), new.splitlines())
                        delta = list(diff)
                        # print(delta)
                        self.bot.logs.error("global event change %s", str(delta))
                        self.messageids[mi] = info.message
                        mc = len(delta) + 1
                if all(key in ["title", "message"] for key in listv):
                    if tc or mc > 0:
                        embed = Embeds.globalEventEmbed(
                            info, f"changed_{tc},{mc}", ",".join(listv)
                        )
                else:
                    embed = Embeds.globalEventEmbed(info, "changed", ",".join(listv))
            # elif place == "news": embed = Embeds.NewsFeedEmbed(info, "Changed")
            elif place == "resources":
                if "currentValue" in dump and len(list(dump.keys())) == 1:
                    if info.retrieved_at.minute % 15 != 0:
                        return None
                    embed = Embeds.resourceEmbed(info, "changed", "")
                    embed.title = "ResourceChange"
                    embed.set_author(
                        name=f"{embed._author['name']} at wt {item['game_time']}"
                    )
                    return embed
                embed = Embeds.resourceEmbed(info, "changed", "")
        if embed:
            embed.set_author(name=f"{embed._author['name']} at wt {item['game_time']}")
        return embed

    @process_game_events.error
    async def logerror(self, ex):
        await self.bot.send_error(ex, "LOG ERROR FOR POST", True)

    async def updatelog(self):
        """TC_TASK, Runs every minute on the dot."""
        try:
            if not self.get_running:
                task = asyncio.create_task(self.load_log())
            else:
                self.bot.logs.warning("LOG UPDATE WARNING: CANNOT SCHEDULE CALL!")

        except Exception as e:
            self.get_running = False
            await self.bot.send_error(e, "LOG ERROR", True)
            self.get_running = False

    async def load_log(self):
        """Ran within update_log"""
        try:
            await asyncio.wait_for(self.main_log(), timeout=60)
        except Exception as e:
            self.get_running = False
            await self.bot.send_error(e, "LOG ERROR OUTER", True)
            self.get_running = False

    async def main_log(self):
        """
        Load results from api.
        """

        # 1: GET WEBHOOKS.
        if not self.loghook:
            hooks = ServerHDProfile.get_entries_with_webhook()
            lg = [AssetLookup.get_asset("loghook", "urls")]
            for h in hooks:
                lg.append(h)
            self.redirect_hook = AssetLookup.get_asset("subhook", "urls")
            self.loghook = lg

        self.get_running = True
        if self.test_with:
            # Code for testing the auto log.
            if self.spot >= len(self.test_with):
                return
            lastwar = self.test_with[self.spot - 1]
            now = self.test_with[self.spot]
            events, warstat = await self.apistatus.get_now(lastwar, self.QueueAll, now)

            self.spot += 1
            if events:
                item = GameEvent(
                    mode=EventModes.GROUP,
                    place="GROUP",
                    batch=501,
                    value=events,
                )
                await self.QueueAll.put([item])

            self.apistatus.warall = warstat
        else:
            events, warstat = await self.apistatus.get_now(
                self.apistatus.warall, self.QueueAll, None, None
            )
            if events:
                item = GameEvent(
                    mode=EventModes.GROUP,
                    place="GROUP",
                    batch=501,
                    value=events,
                )
                await self.QueueAll.put([item])
        self.get_running = False

    @commands.is_owner()
    @commands.command(name="now_test")
    async def load_test_now(self, ctx: commands.Context):
        await self.load_log()
        await ctx.send("Done testing now.")

    @commands.is_owner()
    @commands.command(name="get_last_recorded_positions")
    async def get_last_recorded_positions(self, ctx: commands.Context):
        await self.send_last_planet_positions()
        await ctx.send("Last Planet Positions sent through Auto Log Embeds.")

    @commands.is_owner()
    @commands.command(name="planeteffectget")
    async def peffect(self, ctx: commands.Context):
        await process_planet_attacks(
            self.apistatus.warall.status.planetActiveEffects,
            [],
            "planetEffects",
            ["index", "galacticEffectId"],
            self.QueueAll,
            1234567890,
        )
        await ctx.send("Done testing now.")

    @property
    def apistatus(self) -> hd2.ApiStatus:
        return self.bot.get_cog("HelldiversCog").apistatus


async def setup(bot):
    module_name = "cogs.HD2AutoLog"

    await bot.add_cog(HelldiversAutoLog(bot))


async def teardown(bot):
    await bot.remove_cog("HelldiversAutoLog")
