import asyncio
import json
import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import discord
from dateutil.rrule import MINUTELY, rrule
from discord.ext import commands, tasks
import os
import re
import cogs.HD2 as hd2
from cogs.HD2.db import ServerHDProfile
from cogs.HD2.helldive.models.ABC.model import BaseApiModel
from assetloader import AssetLookup

# import datetime
from bot import (
    TC_Cog_Mixin,
    TCBot,
)
from cogs.HD2.helldive.models.ABC.utils import hdml_parse

from utility import WebhookMessageWrapper as web
from bot.Tasks import TCTask, TCTaskManager


from discord.utils import format_dt as fdt


from cogs.HD2.helldive import (
    DiveharderAll,
    NewsFeedItem,
    PlanetStatus,
    PlanetInfo,
    PlanetEvent,
    Campaign,
    Planet,
    GlobalEvent,
    SectorStates,
    PlanetAttack,
    SimplePlanet,
    PlanetActiveEffects,
    KnownPlanetEffect,
    build_planet_effect,
)

from cogs.HD2.helldive.constants import faction_names
from cogs.HD2.maths import maths
from cogs.HD2.diff_util import process_planet_attacks, GameEvent
from utility.manual_load import load_json_with_substitutions


class PlanetEvents:
    def __init__(self, planet: Planet) -> None:
        self.planet: Planet = planet
        self.planet_event: Optional[str] = None
        self.planet1: Optional[str] = None
        self.lastInfo: Dict[str, Any] = {}
        self.lastStatus: Dict[str, Any] = {}
        self.evt: List[Dict[str, Any]] = []
        self.trig: List[str] = []
        self.ret = None

    def add_event(self, event: GameEvent, key: str) -> None:
        self.evt.append(event)
        if event["mode"] in ["new", "remove"]:
            self.ret = event["value"].retrieved_at
            if event["place"] == "planetevents":
                self.planet_event = event["value"]
        elif event["mode"] == "change":
            self.ret = event["value"][0].retrieved_at

        if key not in self.trig:
            self.trig.append(key)

    def get_links(self) -> Tuple[List[int], List[int]]:
        new, old = [], []
        if "waypoints" in self.lastInfo:
            for i, v in self.lastInfo["waypoints"].items():
                for t, ind in v.items():
                    if t == "new":
                        new.append(ind)
                    if t == "old":
                        old.append(ind)
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


class SectorEvents:
    def __init__(self, planet: SectorStates) -> None:
        self.planet: SectorStates = planet
        self.planet_event = None
        self.lastInfo: Dict[str, Any] = {}
        self.lastStatus: Dict[str, Any] = {}
        self.evt: List[Dict[str, Any]] = []
        self.trig: List[str] = []
        self.ret = None

    def add_event(self, event: GameEvent, key: str) -> None:
        self.evt.append(event)
        if event.mode in ["new", "remove"]:
            self.ret = event.value.retrieved_at
        elif event.mode == "change":
            self.ret = event.value[0].retrieved_at
        if key not in self.trig:
            self.trig.append(key)


class GeneralEvents:
    def __init__(self) -> None:
        self.evt: List[Dict[str, Any]] = []
        self.trig: List[str] = []
        self.ret = None

    def add_event(self, event: GameEvent, key: str) -> None:
        self.evt.append(event)
        if event.mode in ["new", "remove"]:
            self.ret = event.value.retrieved_at
        elif event.mode == "change":
            self.ret = event.value[0].retrieved_at

        if key not in self.trig:
            self.trig.append(key)


faction_dict = {1: "Human", 2: "Terminid", 3: "Automaton", 4: "Illuminate"}


class Batch:
    def __init__(self, batch_id: str) -> None:
        self.batch_id: str = batch_id
        self.time: datetime.datetime = datetime.datetime.now()
        self.planets: Dict[str, PlanetEvents] = {}
        self.hd2: Dict[str, Any] = load_json_with_substitutions(
            "./assets/json", "logreasons.json", {}
        )
        print(self.hd2)
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
        if sector_name is not None:
            if sector_name not in self.sector:
                self.sector[sector_name] = SectorEvents(planet)
            self.sector[sector_name].add_event(event, key)
        elif planet_name is not None:
            if planet_name not in self.planets:
                print("Adding ", planet_name)
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
        mode: str = event.mode
        place: str = event.place
        value: Any = event.value
        planet_name_source: Optional[str] = None
        sector_name: Optional[str] = None
        planet: Optional[Planet] = None

        key: str = f"{place}_{mode}"
        print(key)

        if place in ["campaign", "planetevents"]:
            va = value
            if mode == "change":
                va, _ = value
            planet = SimplePlanet.from_index(va.planetIndex)
            # planet = apistatus.planets.get(int(value.planetIndex), None)
            if planet:
                planet_name_source = planet.get_name(False)

        if place in ["planets", "planetInfo"]:
            va, _ = value
            # planet = apistatus.planets.get(int(va.index), None)

            planet = SimplePlanet.from_index(va.index)
            if planet:
                planet_name_source = planet.get_name(False)

        if place in ["sectors"]:
            va, _ = value
            planet = va
            if planet:
                sector_name = va.name

        if place in ["planetAttacks"]:
            pass
            # planet_source = apistatus.planets.get(int(value.source), None)
            # planet_target = apistatus.planets.get(int(value.target), None)
            # if planet_source:
            #     planet_name_source = planet_source.get_name(False)
            # if planet_target:
            #     planet = planet_target

        self.add_event(event, planet_name_source, key, planet, sector_name)

        if mode == "change" and place != "sectors":
            self.update_planet(planet_name_source, value, place)
        if mode == "change" and place == "sectors":
            pass

    def format_combo_text(
        self, ctype: str, planet_data: PlanetEvents, ctext: List[List[str]]
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
                target = target.replace("[PLANET 1]", planets_data_json[str(i)]["name"])
                target = target.replace("[SECTOR 1]", planet_data.planet.sector)
                target = target.replace(
                    "[FACTION]",
                    faction_dict.get(planet_data.planet.owner, "UNKNOWN")
                    + str(planet_data.planet.owner),
                )
                target += f" ({custom_strftime(planet_data.ret)})"
                targets.append(target)
        else:
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

    def combo_checker(self) -> List[str]:
        """Check for event combos"""
        combos: List[str] = []

        for planet_data in self.planets.values():
            trig_list: List[str] = planet_data.trig
            combos.append(
                str(planet_data.planet.name) + ": `" + ",".join(trig_list) + "`"
            )
            combo: Optional[List[str]] = self.check_trig_combinations(
                trig_list, planet_data
            )
            if combo:
                for c in combo:

                    if c in self.hd2:
                        text: List[str] = self.format_combo_text(
                            c, planet_data, self.hd2[c]
                        )
                        print(text)
                        combos.extend(text)
                    else:
                        combos.append(str(c))
        for sector_data in self.sector.values():
            trig_list: List[str] = sector_data.trig
            combos.append(str(sector_data.planet.name) + ":" + ",".join(trig_list))

            combo: Optional[List[str]] = self.check_sector_trig_combinations(
                trig_list, sector_data
            )
            if combo:
                for c in combo:
                    if c in self.hd2:
                        text: List[str] = self.format_combo_text(
                            c, sector_data, self.hd2[c]
                        )
                        print(text)
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

    def check_trig_combinations(
        self, trig_list: List[str], planet_data: PlanetEvents
    ) -> List[str]:
        planet: Planet = planet_data.planet
        combinations: List[str] = []
        if "campaign_new" in trig_list and "planetevents_new" not in trig_list:
            combinations.append("cstart")

        if self.contains_all_values(trig_list, ["campaign_new", "planetevents_new"]):
            combinations.append("defense start")
        if "campaign_remove" in trig_list and len(trig_list) == 1:
            combinations.append("cend")

        if self.contains_all_values(trig_list, ["campaign_remove", "planets_change"]):

            if planet and planet.owner == 1:
                new, old = planet_data.get_last_planet_owner()
                if old != new:
                    combinations.append("planet won")

        if self.contains_all_values(
            trig_list, ["campaign_remove", "planetevents_remove", "planets_change"]
        ):
            if planet and planet.owner != 1:

                combinations.append("defense lost")

        if (
            self.contains_all_values(
                trig_list, ["campaign_remove", "planetevents_remove"]
            )
            and "planets_change" not in trig_list
        ):
            combinations.append("defense won")

        if self.contains_all_values(
            trig_list, ["campaign_remove", "planetevents_remove", "planets_change"]
        ):
            if planet and planet.owner == 1:
                combinations.append("defense won")

        if "planets_change" in trig_list and "campaign_remove" not in trig_list:
            if planet and planet.owner != 1:
                new, old = planet_data.get_last_planet_owner()
                if old != new:
                    combinations.append("planet flip")

        if "planets_change" in trig_list:
            pass
            # combinations.append("pcheck")

        if any(
            value in trig_list for value in ["planetInfo_change"]
        ) and self.is_new_link(planet, planet_data):
            combinations.append("newlink")

        if any(
            value in trig_list for value in ["planetInfo_change"]
        ) and self.is_destroyed_link(planet, planet_data):
            combinations.append("destroylink")

        return combinations if combinations else None

    def check_sector_trig_combinations(
        self, trig_list: List[str], planet_data: SectorEvents
    ) -> Optional[List[str]]:
        combinations: List[str] = []
        if "sectors_change" in trig_list:
            combinations.append("sector_state")

        return combinations if combinations else None

    def is_new_link(self, planet: Planet, target_planet: PlanetEvents) -> bool:
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
            description=f"A campaign has {mode} for **{name}**, in sector **{sector}**.\n{strc}\nTimestamp:{fdt(campaign.retrieved_at,'F')}",
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
            description=f"A campaign has {mode} for {name}, in sector {sector}.\n{strc}\nTimestamp:{fdt(campaign.retrieved_at,'F')}",
            timestamp=campaign.retrieved_at,
            color=color,
        )
        emb.set_author(name=f"Campaign {mode}.")
        emb.set_footer(text=f"{strc},{custom_strftime(campaign.retrieved_at)}")
        return emb

    @staticmethod
    def deadzoneWarningEmbed(campaign: BaseApiModel, mode="started") -> discord.Embed:
        emb = discord.Embed(
            title=f"DEADZONE DETECTED",
            description=f"A likely deadzone was detected!\nTimestamp:{fdt(campaign.retrieved_at,'F')}",
            timestamp=campaign.retrieved_at,
            color=0xFF0000,
        )
        emb.set_author(name=f"DEADZONE WARNING.")
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
            description=f"An attack has {mode} from {source_name} to {target_name}.   \nTimestamp:{fdt(atk.retrieved_at,'F')}",
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
            title=f"Planet Attacks",
            description="\n".join([f"* {s}" for s in strings]),
            timestamp=timestamp,
            color=0x707CC8 if mode == "added" else 0xC08888,
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
            description=f"A new event has {mode} for {name}, in sector {sector}.   \nTimestamp:{fdt(campaign.retrieved_at,'F')}",
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
            description=f"An Effect was {mode} for {name}, in sector {sector}.\n\n Timestamp:{fdt(campaign.retrieved_at,'F')}",
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
        emb.add_field(name="Timestamp", value=f"Timestamp:{fdt(evt.retrieved_at,'F')}")
        emb.set_author(name=f"Global Event {mode}.")
        emb.set_footer(
            text=f"{footerchanges},EID:{evt.eventId}, {custom_strftime(evt.retrieved_at)}"
        )
        return emb

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
            specialtext += f"\n* Owner: `{faction_names.get(old_owner,'er')}`->`{faction_names.get(new_owner,'er')}`"
        if "regenPerSecond" in dump:
            old_decay = dump["regenPerSecond"].get("old", 99999)
            new_decay = dump["regenPerSecond"].get("new", 99999)
            old_decay = round(maths.dps_to_lph(old_decay), 3)
            new_decay = round(maths.dps_to_lph(new_decay), 3)
            specialtext += f"\n* Regen Rate: `{old_decay}`->`{new_decay}`"

        emb = discord.Embed(
            title=f"{name} Field Change",
            description=f"Stats changed for {name}, in sector {sector}.\n{specialtext}\n```{globtex[:3500]}```",
            timestamp=campaign.retrieved_at,
            color=color,
        )
        emb.add_field(
            name="Timestamp", value=f"Timestamp:{fdt(campaign.retrieved_at,'F')}"
        )
        emb.set_author(name=f"Planet Value Change")
        emb.set_footer(text=f"{custom_strftime(campaign.retrieved_at)}")
        return emb

    @staticmethod
    def dumpEmbed(
        campaign: BaseApiModel, dump: Dict[str, Any], name: str, mode="started"
    ) -> discord.Embed:
        globtex = json.dumps(dump, default=str)
        emb = discord.Embed(
            title=f"UNSEEN API Change",
            description=f"Field changed for {name}\n```{globtex[:4000]}```",
            timestamp=campaign.retrieved_at,
            color=0x000054,
        )
        emb.add_field(
            name="Timestamp", value=f"Timestamp:{fdt(campaign.retrieved_at,'F')}"
        )
        emb.set_author(name=f"API Value Change")
        emb.set_footer(text=f"{custom_strftime(campaign.retrieved_at)}")
        return emb

    @staticmethod
    def NewsFeedEmbed(newsfeed: NewsFeedItem, mode="started") -> discord.Embed:
        title, desc = newsfeed.to_str()
        emb = discord.Embed(
            title=f"{title}",
            description=desc,
            timestamp=newsfeed.retrieved_at,
            color=0x222222,
        )
        emb.add_field(
            name="Timestamp", value=f"Timestamp:{fdt(newsfeed.retrieved_at,'F')}"
        )
        emb.set_author(name=f"New dispatch from Super Earth...")
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
        robj2 = rrule(freq=MINUTELY, interval=1, dtstart=st)
        self.QueueAll = asyncio.Queue()
        self.EventQueue = asyncio.Queue()
        self.PlanetQueue = asyncio.Queue()
        if not TCTaskManager.does_task_exist("UpdateLog"):
            self.tc_task2 = TCTask("UpdateLog", robj2, robj2.after(st))
            self.tc_task2.assign_wrapper(self.updatelog)
        self.run2.start()

    def cog_unload(self):
        TCTaskManager.remove_task("UpdateLog")
        self.run2.cancel()
        hold = {"titles": self.titleids, "messages": self.messageids}
        hd2.save_to_json(hold, "./saveData/mt_pairs.json")

    def load_test_files(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        if os.path.exists("./saveData/testwith"):
            for filename in os.listdir("./saveData/testwith"):
                filepath = os.path.join("./saveData/testwith", filename)
                print(filepath)
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

            texts = self.batches[batch_id].combo_checker()
            for t in texts:
                for hook in list(self.loghook):

                    try:
                        await web.postMessageAsWebhookWithURL(
                            hook,
                            message_content=t,
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
    async def run2(self):
        try:
            try:
                item = self.QueueAll.get_nowait()
                await self.send_event_list(item)
                await asyncio.sleep(0.02)
            except asyncio.QueueEmpty:
                pass
            # try:
            #     item = self.PlanetQueue.get_nowait()
            #     if item:
            #         dv = json.dumps(item.value, default=str)
            #         with open("./saveData/outs.jsonl", "a+") as file:
            #             file.write(f"{dv}\n")
            #     await asyncio.sleep(0.02)
            # except asyncio.QueueEmpty:
            #     pass
        except Exception as ex:
            await self.bot.send_error(ex, "LOG ERROR FOR POST", True)

    async def send_event_list(self, item_list: List[GameEvent]):
        embeds: List[discord.Embed] = []
        for item in item_list:
            embed = await self.build_embed(item)
            if embed:
                embeds.append(embed)

        if not embeds:
            return

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
        for embeds in val_batches:
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
                        # ServerHDProfile.set_all_matching_webhook_to_none(hook)

    async def build_embed(self, item: GameEvent):

        event_type = item["mode"]
        if event_type == "group":
            print("group", len(item["value"]))
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
                return embed
        if event_type == "deadzone":
            embed = Embeds.deadzoneWarningEmbed(
                value,
                "started",
            )
        if event_type == "new":
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
            elif place == "globalEvents":
                ti = value.titleId32
                mi = value.messageId32
                tc, mc = False, False
                if value.title and ti != None:
                    if self.titleids.get(ti, None) != value.title:
                        self.titleids[ti] = value.title
                        tc = True
                if value.message and mi != None:
                    if self.messageids.get(mi, None) != value.message:
                        self.messageids[mi] = value.message
                        mc = True
                embed = Embeds.globalEventEmbed(value, "started")
            elif place == "news":
                embed = Embeds.NewsFeedEmbed(value, "started")
        elif event_type == "remove":
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
                if value.title and ti != None:
                    if self.titleids.get(ti, None) != value.title:
                        self.titleids[ti] = value.title
                        tc = True
                if value.message and mi != None:
                    if self.messageids.get(mi, None) != value.message:
                        self.messageids[mi] = value.message
                        mc = True
                embed = Embeds.globalEventEmbed(value, "ended")
            elif place == "news":
                embed = Embeds.NewsFeedEmbed(value, "ended")
        elif event_type == "change":
            (info, dump) = value
            if place == "planets" or place == "planetInfo":
                planet = self.apistatus.planets.get(int(info.index), None)
                if planet:
                    # planets- owner, regenRate
                    embed = Embeds.dumpEmbedPlanet(info, dump, planet, "changed")
                else:
                    embed = Embeds.dumpEmbed(info, dump, "planet", "changed")
            elif place == "stats_raw":
                embed = Embeds.dumpEmbed(info, dump, "stats", "changed")
            elif place == "info_raw":
                embed = Embeds.dumpEmbed(info, dump, "info", "changed")
            elif place == "globalEvents":
                listv = [k for k in dump.keys()]

                ti = info.titleId32
                mi = info.messageId32
                tc, mc = False, False
                if info.title:
                    if self.titleids.get(ti, None) != info.title:
                        self.titleids[ti] = info.title
                        tc = True
                if info.message:
                    if self.messageids.get(mi, None) != info.message:
                        self.messageids[mi] = info.message
                        mc = True
                if all(key in ["title", "message"] for key in listv):

                    if tc or mc:
                        embed = Embeds.globalEventEmbed(
                            info, f"changed_{tc},{mc}", ",".join(listv)
                        )
                else:
                    embed = Embeds.globalEventEmbed(info, "changed", ",".join(listv))

        return embed

    @run2.error
    async def logerror(self, ex):
        await self.bot.send_error(ex, "LOG ERROR FOR POST", True)

    async def updatelog(self):
        try:
            if not self.get_running:
                task = asyncio.create_task(self.load_log())
            else:
                print("NOT SCHEDULING.")

        except Exception as e:
            self.get_running = False
            await self.bot.send_error(e, "LOG ERROR", True)
            self.get_running = False

    async def load_log(self):
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
        if not self.loghook:
            hooks = ServerHDProfile.get_entries_with_webhook()
            lg = [AssetLookup.get_asset("loghook", "urls")]
            for h in hooks:
                lg.append(h)
            self.loghook = lg
        self.get_running = True
        if self.test_with:
            if self.spot >= len(self.test_with):
                return

            lastwar = self.test_with[self.spot - 1]
            now = self.test_with[self.spot]
            events, warstat = await self.apistatus.get_now(lastwar, self.QueueAll, now)

            self.spot += 1
            if events:
                item = GameEvent(
                    mode="group",
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
                    mode="group",
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
