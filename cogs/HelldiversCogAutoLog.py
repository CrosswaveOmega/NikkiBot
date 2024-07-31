import asyncio
import json
import datetime
from typing import Any, Dict, Optional, Union

import discord
from dateutil.rrule import MINUTELY, rrule
from discord.ext import commands, tasks
import os
import re
import cogs.HD2 as hd2
from cogs.HD2.helldive.models.ABC.model import BaseApiModel
from assetloader import AssetLookup

# import datetime
from bot import (
    TC_Cog_Mixin,
    TCBot,
)
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
    PlanetAttack,
)
from utility.manual_load import load_json_with_substitutions


class PlanetEvents:
    def __init__(self, planet):
        self.planet = planet
        self.planet_event = None
        self.planet1 = None
        self.lastInfo = {}
        self.lastStatus = {}
        self.evt = []
        self.trig = []

    def add_event(self, event, key):
        self.evt.append(event)
        if event["place"] == "planetevents":
            self.planet_event = event["value"]

        if key not in self.trig:
            self.trig.append(key)

    def get_links(self):
        new, old = [], []
        if "waypoints" in self.lastInfo:
            for i, v in self.lastInfo["waypoints"].items():
                for t, ind in v.items():
                    if t == "new":
                        new.append(ind)
                    if t == "old":
                        old.append(ind)
        return new, old

    def update_planet(self, value, place):
        v, _ = value
        if place == "planets":
            self.lastStatus = _
            self.planet.owner = v.owner
            self.planet.regenPerSecond = v.regenPerSecond

        elif place == "planetInfo":

            self.lastInfo = _
            self.planet.waypoints = v.waypoints


class GeneralEvents:
    def __init__(self):
        self.evt = []
        self.trig = []

    def add_event(self, event, key):
        self.evt.append(event)
        if key not in self.trig:
            self.trig.append(key)


faction_dict = {1: "Human", 2: "Terminid", 3: "Automaton", 4: "Illuminate"}


class Batch:
    def __init__(self, batch_id):
        self.batch_id = batch_id
        self.time = datetime.datetime.now()
        self.planets = {}
        self.hd2 = load_json_with_substitutions("./assets/json", "logreasons.json", {})
        print(self.hd2)
        self.general = GeneralEvents()

    def add_event(self, event, planet_name, key, planet):
        if planet_name is not None:
            if planet_name not in self.planets:
                self.planets[planet_name] = PlanetEvents(planet)
            self.planets[planet_name].add_event(event, key)
        else:
            self.general.add_event(event, key)

    def update_planet(self, planet_name, value, place):
        if planet_name in self.planets:
            self.planets[planet_name].update_planet(value, place)

    def process_event(self, event, apistatus):
        mode = event["mode"]
        place = event["place"]
        value = event["value"]
        planet_name_source = None
        planet = None

        key = f"{place}_{mode}"
        print(key)

        if place in ["campaign", "planetevents"]:
            planet = apistatus.planets.get(int(value.planetIndex), None)
            if planet:
                planet_name_source = planet.get_name(False)

        if place in ["planets", "planetInfo"]:
            va, _ = value
            planet = apistatus.planets.get(int(va.index), None)
            if planet:
                planet_name_source = planet.get_name(False)

        if place in ["planetAttacks"]:
            planet_source = apistatus.planets.get(int(value.source), None)
            planet_target = apistatus.planets.get(int(value.target), None)
            if planet_source:
                planet_name_source = planet_source.get_name(False)
            if planet_target:
                planet = planet_target

        self.add_event(event, planet_name_source, key, planet)

        if mode == "change":
            self.update_planet(planet_name_source, value, place)

    def format_combo_text(self, ctype, planet_data, ctext):
        targets = []
        data_path = "./hd2json/planets/planets.json"

        with open(data_path, "r") as file:
            planets_data_json = json.load(file)

        if ctype == "newlink":
            new, old = planet_data.get_links()
            for i in new:
                target = ctext[1][0]
                typetext = ctext[2][0]
                target = target.replace("[TYPETEXT]", typetext)
                target = target.replace("[PLANET 0]", planet_data.planet.name)
                target = target.replace("[PLANET 1]", planets_data_json[str(i)]["name"])
                target = target.replace("[SECTOR 1]", planet_data.planet.sector)
                target = target.replace(
                    "[FACTION]", faction_dict.get(planet_data.planet.owner, "UNKNOWN")
                )
                targets.append(target)
        elif ctype == "destroylink":
            new, old = planet_data.get_links()
            for i in old:
                target = ctext[1][0]
                typetext = ctext[2][0]
                target = target.replace("[TYPETEXT]", typetext)
                target = target.replace("[PLANET 0]", planet_data.planet.name)
                target = target.replace("[PLANET 1]", planets_data_json[str(i)])
                target = target.replace("[SECTOR 1]", planet_data.planet.sector)
                target = target.replace(
                    "[FACTION]", faction_dict.get(planet_data.planet.owner, "UNKNOWN")
                )
                targets.append(target)
        else:
            target = ctext[1][0]
            typetext = ctext[2][0]
            target = target.replace("[TYPETEXT]", typetext)
            target = target.replace("[PLANET 0]", planet_data.planet.name)

            # target=target.replace('[PLANET 1]',i)
            target = target.replace("[SECTOR 1]", planet_data.planet.sector)
            if ctype == "defense start":
                if planet_data.planet_event:
                    target = target.replace(
                        "[FACTION]",
                        faction_dict.get(planet_data.planet_event.race, "UNKNOWN"),
                    )
            else:
                target = target.replace(
                    "[FACTION]", faction_dict.get(planet_data.planet.owner, "UNKNOWN")
                )
            targets.append(target)
        return targets

    def combo_checker(self):
        combos = []

        for planet_data in self.planets.values():
            trig_list = planet_data.trig
            combo = self.check_trig_combinations(trig_list, planet_data)
            if combo:
                for c in combo:
                    print(c)
                    combos.append(str(c))
                    if c in self.hd2:
                        text = self.format_combo_text(c, planet_data, self.hd2[c])
                        print(text)
                        combos.extend(text)

                # combos.extend(combo)

        return combos

    def contains_all_values(self, input_list, target_list):
        for value in target_list:
            if value not in input_list:
                return False
        return True

    def check_trig_combinations(self, trig_list, planet_data: PlanetEvents):
        planet = planet_data.planet
        combinations = []
        print(planet.index, trig_list)

        if "campaign_new" in trig_list and "planetevents_new" not in trig_list:
            combinations.append("cstart")

        if self.contains_all_values(trig_list, ["campaign_new", "planetevents_new"]):
            combinations.append("defense start")
        if (
            all(value in trig_list for value in ["campaign_remove"])
            and len(trig_list) == 1
        ):
            combinations.append("cend")

        if all(value in trig_list for value in ["campaign_remove", "planets_change"]):
            if planet and planet.owner == 1:
                combinations.append("planet won")

        if all(
            value in trig_list
            for value in ["campaign_remove", "planetevents_remove", "planets_change"]
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

        if (
            all(value in trig_list for value in ["planets_change"])
            and "campaign_remove" not in trig_list
        ):
            if planet and planet.owner != 1:
                combinations.append("planet flip")

        if all(value in trig_list for value in ["planets_change"]):
            combinations.append("pcheck")

        if any(
            value in trig_list for value in ["planetInfo_change"]
        ) and self.is_new_link(planet, planet_data):
            combinations.append("newlink")

        if any(
            value in trig_list for value in ["planetInfo_change"]
        ) and self.is_destroyed_link(planet, planet_data):
            combinations.append("destroylink")

        return combinations if combinations else None

    def is_new_link(self, planet, target_planet):
        if target_planet:
            new, old = target_planet.get_links()
            if new:
                return True
        return False

    def is_destroyed_link(self, planet, target_planet):
        if target_planet:
            new, old = target_planet.get_links()
            if old:
                return True
        return False


def check_platform():

    if os.name == "nt":
        return "%#I:%M%p UTC %b {S} %Y"
    return "%-I:%M%p UTC %b {S} %Y"


def suffix(d):
    return {1: "st", 2: "nd", 3: "rd"}.get(d % 20, "th")


def custom_strftime(t):
    format = "%#I:%M%p UTC %b {S} %Y"
    out = t.strftime(format).replace("{S}", str(t.day) + suffix(t.day))
    out = out.replace("AM", "am")
    out = out.replace("PM", "pm")
    return out


pattern = r"<i=1>(.*?)<\/i>"
pattern3 = r"<i=3>(.*?)<\/i>"


class Embeds:
    @staticmethod
    def campaignLogEmbed(
        campaign: Campaign, planet: Optional[Planet], mode="started"
    ) -> discord.Embed:
        strc = hd2.embeds.create_campaign_str(campaign)
        name, sector = campaign.planetIndex, None
        if planet:
            name, sector = planet.get_name(False), planet.sector
        emb = discord.Embed(
            title=f"Campaign Detected",
            description=f"A campaign has {mode} for {name}, in sector {sector}.  \nTimestamp:{fdt(campaign.retrieved_at,'F')}",
            timestamp=campaign.retrieved_at,
        )
        emb.set_author(name=f"Campaign {mode}.")
        emb.set_footer(text=f"{strc},{custom_strftime(campaign.retrieved_at)}")
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
            title=f"Planet Attack Detected",
            description=f"An attack has {mode} from {source_name} to {target_name}.   \nTimestamp:{fdt(atk.retrieved_at,'F')}",
            timestamp=atk.retrieved_at,
        )
        emb.set_author(name=f"Planet Attack {mode}.")
        emb.set_footer(text=f"{custom_strftime(atk.retrieved_at)}")
        return emb

    @staticmethod
    def planeteventsEmbed(
        campaign: PlanetEvent, planet: Optional[Planet], mode="started"
    ) -> discord.Embed:
        name, sector = campaign.planetIndex, None
        if planet:
            name, sector = planet.get_name(False), planet.sector
        emb = discord.Embed(
            title=f"Planet Event Detected",
            description=f"A new event has {mode} for {name}, in sector {sector}.   \nTimestamp:{fdt(campaign.retrieved_at,'F')}",
            timestamp=campaign.retrieved_at,
        )
        emb.add_field(name="Event Details", value=campaign.long_event_details())
        emb.set_author(name=f"Planet Event {mode}.")
        emb.set_footer(
            text=f"EID:{campaign.id}, {custom_strftime(campaign.retrieved_at)}"
        )
        return emb

    @staticmethod
    def globalEventEmbed(evt: GlobalEvent, mode="started") -> discord.Embed:
        globtex = ""
        title = ""
        if evt.title:
            mes = re.sub(pattern, r"**\1**", evt.title)
            mes = re.sub(pattern3, r"***\1***", mes)
            globtex += f"### {mes}\n"
        if evt.message:
            mes = re.sub(pattern, r"**\1**", evt.message)
            mes = re.sub(pattern3, r"***\1***", mes)
            globtex += f"{mes}\n\n"
        emb = discord.Embed(
            title=f"Global Event Detected",
            description=f"A global event has {mode}.\n{globtex}",
            timestamp=evt.retrieved_at,
        )
        emb.add_field(name="Event Details", value=evt.strout())
        emb.add_field(name="Timestamp", value=f"Timestamp:{fdt(evt.retrieved_at,'F')}")
        emb.set_author(name=f"Global Event {mode}.")
        emb.set_footer(text=f"EID:{evt.eventId}, {custom_strftime(evt.retrieved_at)}")
        return emb

    @staticmethod
    def dumpEmbedPlanet(
        campaign: Union[PlanetStatus, PlanetInfo],
        dump: Dict[str, Any],
        planet: Optional[Planet],
        mode="started",
    ) -> discord.Embed:
        name, sector = "?", None
        if planet:
            name, sector = planet.get_name(False), planet.sector
        globtex = json.dumps(dump)
        emb = discord.Embed(
            title=f"Planet Field Change",
            description=f"Stats changed for {name}, in sector {sector}.\n```{globtex[:4000]}```",
            timestamp=campaign.retrieved_at,
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
        globtex = json.dumps(dump)
        emb = discord.Embed(
            title=f"API Change",
            description=f"Field changed for {name}\n```{globtex[:4000]}```",
            timestamp=campaign.retrieved_at,
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
        self.loghook = AssetLookup.get_asset("loghook", "urls")
        self.get_running = False
        self.event_log = []
        self.spot = 1
        self.batches: dict[int, Batch] = {}
        self.test_with = []
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
        if not TCTaskManager.does_task_exist("UpdateLog"):
            self.tc_task2 = TCTask("UpdateLog", robj2, robj2.after(st))
            self.tc_task2.assign_wrapper(self.updatelog)
        self.run2.start()

    def cog_unload(self):
        TCTaskManager.remove_task("UpdateLog")
        self.run2.cancel()

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

    @tasks.loop(seconds=5)
    async def run2(self):
        events = []
        run_ok = True
        while run_ok:
            try:
                item = self.QueueAll.get_nowait()
                # await self.EventQueue.put(item)
                events.append(item)
                await self.run(item)

                await asyncio.sleep(0.02)
            except asyncio.QueueEmpty:
                run_ok = False

        if events:
            print("once")

            pass
        try:
            await self.batch_events_2(events)
        except Exception as ex:
            await self.bot.send_error(ex, "LOG ERROR", True)

    async def batch_events_2(self, events):
        for event in events:
            batch_id = event["batch"]
            if batch_id not in self.batches:
                self.batches[batch_id] = Batch(batch_id)
            self.batches[batch_id].process_event(event, self.apistatus)

        for batch_id in list(self.batches.keys()):
            if datetime.datetime.now() - self.batches[
                batch_id
            ].time > datetime.timedelta(seconds=16):
                texts = self.batches[batch_id].combo_checker()
                for t in texts:
                    await web.postMessageAsWebhookWithURL(
                        self.loghook,
                        message_content=t,
                        display_username="SUPER EVENT",
                        avatar_url=self.bot.user.avatar.url,
                    )
                self.batches.pop(batch_id)

        return self.batches

    async def run(self, item):
        event_type = item["mode"]
        batch = item["batch"]
        place = item["place"]
        value = item["value"]
        embed = None

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
            elif place == "globalEvents":
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
            elif place == "globalEvents":
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

        if embed:
            # print(embed.description)
            await web.postMessageAsWebhookWithURL(
                self.loghook,
                message_content="",
                display_username="Super Earth Event Log",
                avatar_url=self.bot.user.avatar.url,
                embed=[embed],
            )

    @run2.error
    async def logerror(self, ex):
        await self.bot.send_error(ex, "LOG ERROR", True)

    async def updatelog(self):
        try:
            if not self.get_running:
                task = asyncio.create_task(self.load_log())
            else:
                print("NOT SCHEDULING.")

        except Exception as e:
            await self.bot.send_error(e, "LOG ERROR", True)

    async def load_log(self):
        try:
            await asyncio.wait_for(self.main_log(), timeout=60)
        except Exception as e:
            await self.bot.send_error(e, "LOG ERROR", True)
            self.get_running = False

    async def main_log(self):
        # print(self.spot,self.test_with)
        self.get_running = True
        if self.test_with:
            if self.spot >= len(self.test_with):
                return

            lastwar = self.test_with[self.spot - 1]
            now = self.test_with[self.spot]
            nowval, warstat = await self.apistatus.get_now(lastwar, self.QueueAll, now)

            if nowval:
                pass
            self.spot += 1

            self.apistatus.warall = warstat
        else:
            nowval, warstat = await self.apistatus.get_now(
                self.apistatus.warall, self.QueueAll, None
            )
        self.get_running = False

    @commands.is_owner()
    @commands.command(name="now_test")
    async def load_test_now(self, ctx: commands.Context):
        await self.load_log()
        await ctx.send("Done testing now.")

    @property
    def apistatus(self) -> hd2.ApiStatus:
        return self.bot.get_cog("HelldiversCog").apistatus


async def setup(bot):
    module_name = "cogs.HD2AutoLog"

    await bot.add_cog(HelldiversAutoLog(bot))


async def teardown(bot):
    await bot.remove_cog("HelldiversAutoLog")
