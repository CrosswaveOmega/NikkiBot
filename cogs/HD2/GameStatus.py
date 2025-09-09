import asyncio
import csv
import datetime
import json
import os
from typing import *

import gui
from utility.debug import Timer

from .diff_util import detect_loggable_changes, detect_loggable_changes_planet
from hd2api import *
from .utils import prioritized_string_split
from discord.utils import format_dt as fdt
from hd2api import extract_timestamp as et
from hd2api.util.utils import set_status_emoji

MAX_ATTEMPT = 3

status_emoji: Dict[str, str] = {
    "onc": "<:checkboxon:1199756987471241346>",
    "noc": "<:checkboxoff:1199756988410777610>",
    "emptyc": "<:checkboxempty:1199756989887172639>",
    "edit": "<:edit:1199769314929164319>",
    "add": "<:add:1199770854112890890>",
    "automaton": "<:bots:1241748819620659332>",
    "terminids": "<:bugs:1241748834632208395>",
    "humans": "<:superearth:1275126046869557361>",
    "illuminate": "<:squid:1274752443246448702>",
    "hdi": "<:hdi:1240695940965339136>",
    "medal": "<:Medal:1241748215087235143>",
    "req": "<:rec:1274481505611288639>",
    "credits": "<:supercredit:1274728715175067681>",
}


def lmj(directory_path: str):
    """
    Load all JSON files from the specified directory into a single dictionary.
    Args:
    - directory_path (str): Path to the directory containing JSON files.
    Returns:
    - dict: A dictionary where keys are file names (without extension) and values are loaded JSON data.
    """
    planets_data = {}
    # Validate directory path
    if not os.path.isdir(directory_path):
        raise ValueError(f"Directory '{directory_path}' does not exist.")
    # Load JSON files
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            file_path = os.path.join(directory_path, filename)
            with open(file_path, "r", encoding="utf8") as f:
                try:
                    json_data = json.load(f)
                    # Remove file extension from filename
                    file_key = os.path.splitext(filename)[0]
                    planets_data[file_key] = json_data
                except json.JSONDecodeError as e:
                    gui.gprint(f"Error loading JSON from {filename}: {e}")
    return planets_data


class LimitedSizeList(list):
    """A list that can only have a fixed amount of elements."""

    def __init__(self, max_size):
        self.max_size = max_size
        self.items: List[
            Union[War, Assignment2, Campaign2, GlobalResource, Region]
        ] = []

    def add(self, item):
        if len(self.items) >= self.max_size:
            self.items.pop()
        self.items.insert(0, item)

    def push(self, item):
        if len(self.items) >= self.max_size:
            self.items.pop(0)
        self.items.append(item)

    def get_changes(
        self,
    ) -> List[Union[War, Assignment2, Campaign2, GlobalResource, Region]]:
        """return a list of all differences between items in this limited sized list."""
        curr, this = None, []
        for i in self.items:
            if curr is None:
                curr = i
            else:
                this.append(i - curr)
                curr = i
        return this

    def get_first_change(self):
        if len(self.items) > 1:
            return (self.items[0], self.items[1])
        if len(self.items) == 0:
            return None, None
        return self.items[0], self.items[0]

    def get_change_from(self, mins=15):
        """Retrieve item from a specified number of minutes ago."""
        if not self.items or mins <= 0:
            return None
        if len(self.items) <= 1:
            return (self.items[0], self.items[0])
        current_time = self.items[0].retrieved_at

        target_time = current_time - datetime.timedelta(minutes=mins)

        for item in self.items:
            if hasattr(item, "retrieved_at") and item.retrieved_at <= target_time:
                return (self.items[0], item)
        return (self.items[0], self.items[1])

    def get_first(self):
        return self.items[0]

    def __repr__(self):
        return repr(self.items)

    def __len__(self):
        return len(self.items)


class ApiStatus:
    """
    A container class for information retrieved from Helldivers 2's api.
    """

    __slots__ = [
        "client",
        "max_list_size",
        "war",
        "campaigns",
        "assignments",
        "resources",
        "planets",
        "regions",
        "dispatches",
        "last_planet_get",
        "statics",
        "warall",
        "direct",
        "nowval",
        "getlock",
        "stations",
        "last_station_time",
        "ignore_these",
        "deadzone",
    ]

    def __init__(self, client: APIConfig = APIConfig(), max_list_size=8, direct=True):
        set_status_emoji(status_emoji)
        self.client = client
        self.max_list_size = max_list_size
        self.direct = direct
        self.war: LimitedSizeList[War] = LimitedSizeList(self.max_list_size)
        self.assignments: Dict[int, LimitedSizeList[Assignment2]] = {}
        self.campaigns: Dict[int, LimitedSizeList[Campaign2]] = {}
        self.resources: Dict[int, LimitedSizeList[GlobalResource]] = {}

        self.regions: Dict[int, LimitedSizeList[Region]] = {}
        self.planets: Dict[int, Planet] = {}
        self.dispatches: List[Dispatch] = []
        self.last_planet_get: datetime.datetime = datetime.datetime(2024, 1, 1, 0, 0, 0)
        self.warall: DiveharderAll = None
        self.nowval = DiveharderAll(status=WarStatus(), war_info=WarInfo())
        planetjson = lmj("./hd2json/planets")
        effectjson = lmj("./hd2json/effects")
        self.statics = StaticAll(
            galaxystatic=GalaxyStatic(**planetjson),
            effectstatic=EffectStatic(**effectjson),
        )
        self.stations = {}
        self.ignore_these = []
        self.last_station_time = datetime.datetime(2024, 1, 1, 1, 1, 0)
        self.getlock = asyncio.Lock()
        self.deadzone = False

    def to_dict(self):
        return {
            "max_list_size": self.max_list_size,
            "war": [w.model_dump(exclude="time_delta") for w in self.war.items],
            "assignments": {
                k: [item.model_dump(exclude="time_delta") for item in v.items]
                for k, v in self.assignments.items()
            },
            "resources": {
                k: [item.model_dump(exclude="time_delta") for item in v.items]
                for k, v in self.resources.items()
            },
            "regions": {
                k: [item.model_dump(exclude="time_delta") for item in v.items]
                for k, v in self.regions.items()
            },
            "campaigns": {
                k: [item.model_dump(exclude="time_delta") for item in v.items]
                for k, v in self.campaigns.items()
            },
            "planets": {
                k: p.model_dump(exclude="time_delta") for k, p in self.planets.items()
            },
            "stations": {
                k: p.model_dump(exclude="time_delta") for k, p in self.stations.items()
            },
            "dispatches": [d.model_dump(exclude="time_delta") for d in self.dispatches],
            "warall": self.warall.model_dump(exclude="time_delta"),
        }

    @property
    def warstat(self):
        if self.warall:
            return self.warall.status
        return None

    @classmethod
    def from_dict(cls, data, client: APIConfig = APIConfig()):
        newcks = cls(client=client)
        newcks.max_list_size = data["max_list_size"]
        newcks.war = LimitedSizeList(newcks.max_list_size)
        for val in data["war"]:
            newcks.war.push(War(**val))
        newcks.assignments = {}
        for k, v in data["assignments"].items():
            assignment_list = LimitedSizeList(newcks.max_list_size)
            for item in v:
                assignment_list.push(Assignment2(**item))
            newcks.assignments[int(k)] = assignment_list
        newcks.campaigns = {}
        for k, v in data["campaigns"].items():
            campaign_list = LimitedSizeList(newcks.max_list_size)
            for item in v:
                campaign_list.push(Campaign2(**item))
            newcks.campaigns[int(k)] = campaign_list
        if "resources" in data:
            for k, v in data["resources"].items():
                resource_list = LimitedSizeList(newcks.max_list_size)
                for item in v:
                    resource_list.push(GlobalResource(**item))
                newcks.resources[int(k)] = resource_list
        if "regions" in data:
            for k, v in data["regions"].items():
                resource_list = LimitedSizeList(newcks.max_list_size)
                for item in v:
                    resource_list.push(Region(**item))
                newcks.regions[int(k)] = resource_list
        else:
            newcks.resources = {}
        newcks.planets = {int(k): Planet(**v) for k, v in data["planets"].items()}
        newcks.dispatches = [Dispatch(**d) for d in data["dispatches"]]
        if "warstat" in data:
            newcks.warstat = WarStatus(**data["warstat"])
        if "warall" in data:
            newcks.warall = DiveharderAll(**data["warall"])
        if "stations" in data:
            newcks.stations = {
                int(k): SpaceStation(**v) for k, v in data["stations"].items()
            }
        return newcks

    def __repr__(self):
        s = ""
        s += repr(self.war) + "\n"
        s += repr(self.assignments) + "\n"
        s += repr(self.campaigns) + "\n"
        s += repr(self.warstat) + "\n"
        # s+=repr(self.planets)
        return s

    async def get_war_now(self) -> War:
        war = await GetApiV1War(api_config_override=self.client)
        return war

    async def get_now(
        self,
        current,
        Queue: asyncio.Queue,
        nowval=None,
        PlanetQueue: asyncio.Queue = None,
    ) -> Tuple[Dict[str, Dict[str, Union[List, Dict[str, Any]]]], DiveharderAll]:
        nowv = None
        async with self.getlock:
            if nowval:
                nowv = nowval
            else:
                # Make API CALL
                nowv = await GetApiRawAll(
                    api_config_override=self.client, direct=self.direct
                )
            self.warall = nowv
        if nowv:
            if current:
                with Timer() as timer:
                    diff = await detect_loggable_changes(
                        current,
                        nowv,
                        Queue,
                        self.statics,
                        self.ignore_these,
                    )
                    if PlanetQueue:
                        await detect_loggable_changes_planet(
                            current, nowv, PlanetQueue, self.statics
                        )
                    if diff:
                        self.build_planets()
                gui.gprint("Planet Operation  took", timer.get_time(), "seconds")
                return diff, nowv

        return None, nowv

    async def _update_stations(self):
        active_stations = []
        for s in self.warall.status.spaceStations:
            id = s.id32
            active_stations.append(id)
            self.stations[id] = "READY"
        for k in self.stations.keys():
            id = int(k)
            station = await GetApiDirectSpaceStation(id, self.client)
            self.stations[id] = station

    async def update_stations(self):
        if (datetime.datetime.now() - self.last_station_time) > datetime.timedelta(
            minutes=15
        ):
            await self._update_stations()
            self.last_station_time = datetime.datetime.now()

    async def get_station(self):
        return self.stations
        if (datetime.datetime.now() - self.last_station_time) > datetime.timedelta(
            minutes=15
        ):
            for s in self.warall.status.spaceStations:
                id = s.id32
                station = await GetApiDirectSpaceStation(id, self.client)
                self.stations[id] = station
            self.last_station_time = datetime.datetime.now()
        return self.stations

    async def update_data(self):
        """
        Query the community api, and load the data into the classes.
        """
        war = None
        campaigns = None
        regions = None
        assignments = None
        dispatches = None
        maxattempt = 3
        async with self.getlock:
            self.build_planets()
        try:
            attempt_count = 0
            while attempt_count < maxattempt:
                try:
                    war = build_war(self.warall)
                    break
                except Exception as e:
                    attempt_count += 1
                    await asyncio.sleep(2)
                    if attempt_count >= maxattempt:
                        raise e

            # as1 = await GetApiV1AssignmentsAll(api_config_override=self.client)
            assignments = build_all_assignments(self.warall.major_order)
            campaigns = build_all_campaigns(self.planets, self.warall.status)
            regions = build_all_regions(self.warall, self.statics)

        except Exception as e:
            raise e

        if war is not None:
            self.war.add(war)
        # print(self.assignments, "a2", assignments, "done")
        self.handle_data(assignments, self.assignments, "assignment")
        self.handle_data(campaigns, self.campaigns, "campaign")
        self.handle_data(regions, self.regions, "region")
        self.handle_raw_data(
            self.warall.status.globalResources, self.resources, "Resource"
        )
        try:
            await self.update_stations()
        except Exception as e:
            gui.gprint(e)

            # print(self.warstat)

    def build_planets(self):
        planet_data = {}
        gui.gprint(self.statics.galaxystatic.planets.keys())
        # for i, v in self.statics.galaxystatic.planets.items():
        #     planet = build_planet_2(i, self.warall, self.statics)
        #     planet_data[i] = planet
        self.planets = build_all_planets(self.warall, self.statics)

    def handle_data(
        self,
        data: List[Union[Campaign2, Assignment2, Region]],
        storage: Dict[int, LimitedSizeList],
        data_type: str,
    ) -> None:
        """
        Handle and update data storage, removing stale data entries.

        Args:
            data (List[Union[Campaign2,Assignment2]]): The data to be processed and stored.
            storage (Dict[int, LimitedSizeList]): The storage dictionary where data is kept.
            data_type (str): The type of the data being handled.
        """
        if data is not None:
            data_ids: Set[int] = set()
            for item in data:
                data_ids.add(item.id)
                if item.id not in storage:
                    storage[item.id] = LimitedSizeList(self.max_list_size)
                storage[item.id].add(item)
            key_list = list(storage.keys())
            for k in key_list:
                if k not in data_ids:
                    print(data_type, f"removing {data_type} {k}")
                    storage.pop(k)
        else:
            key_list = list(storage.keys())
            for k in key_list:
                print(data_type, f"removing {data_type} {k}")
                storage.pop(k)

    def handle_raw_data(
        self,
        data: List[Union[GlobalResource]],
        storage: Dict[int, LimitedSizeList],
        data_type: str,
    ) -> None:
        """
        Handle and update data storage, removing stale data entries.

        Args:
            data (List[Union[Campaign2,Assignment2]]): The data to be processed and stored.
            storage (Dict[int, LimitedSizeList]): The storage dictionary where data is kept.
            data_type (str): The type of the data being handled.
        """
        if data is not None:
            data_ids: Set[int] = set()
            for item in data:
                data_ids.add(item.id32)
                if item.id32 not in storage:
                    storage[item.id32] = LimitedSizeList(self.max_list_size)
                storage[item.id32].add(item)
            key_list = list(storage.keys())
            for k in key_list:
                if k not in data_ids:
                    print(data_type, f"removing {data_type} {k}")
                    storage.pop(k)
        else:
            key_list = list(storage.keys())
            for k in key_list:
                print(data_type, f"removing {data_type} {k}")
                storage.pop(k)

    def estimates(self) -> List[Tuple[str, List[str]]]:
        """Estimate the projected liberation/loss times for each campaign,
         and calculate planet liberation amounts at each of those timestamps.

        Returns:
            List[Tuple[str, List[str]]]:
        """
        acts: List[Tuple[Union[Planet, Event], float]] = []
        dates: List[datetime.datetime] = []
        outv: str = ""
        # Get all planets and Events out of the current list of campaigns.
        for _, list in self.assignments.items():
            camp = list.get_first()
            # print(camp.title, camp.briefing)
            dates.append(
                (
                    f"{camp.title}:End at{fdt(et(camp.expiration), 'R')}",
                    et(camp.expiration),
                )
            )

        for _, list in self.campaigns.items():
            camp, _ = list.get_first_change()
            changes = list.get_changes()
            if not changes:
                continue

            avg = Campaign2.average(changes)
            planet: Planet = avg.planet
            dps = camp.planet.calculate_change(planet)
            eps = 0
            if camp.planet.event and planet.event:  # pylint: disable=no-member
                eps = camp.planet.event.calculate_change(
                    planet.event  # pylint: disable=no-member
                )  # pylint: disable=no-member
            if dps == 0 and eps == 0:
                continue
            if dps != 0:
                proj_date = camp.planet.calculate_timeval(dps, dps > 0)
                acts.append((camp.planet, dps))
                dates.append(
                    (
                        f"{camp.planet.get_name()}:{camp.planet.format_estimated_time_string(dps, proj_date)}",
                        proj_date,
                    )
                )
            if eps != 0:
                proj_date = camp.planet.event.calculate_timeval(eps, eps > 0)
                acts.append((camp.planet.event, eps))
                dates.append(
                    (
                        f"{camp.planet.get_name()}:{camp.planet.event.format_estimated_time_string(eps, proj_date)}",
                        proj_date,
                    )
                )
                dates.append(
                    (
                        f"{camp.planet.get_name()}:End at{fdt(et(camp.planet.event.endTime), 'R')}",
                        et(camp.planet.event.endTime),
                    )
                )
        # Sort estimated key dates.
        output_list: List[Tuple[str, List[str]]] = []
        dates.sort(key=lambda x: x[1])
        acts.sort(key=lambda x: x[0].get_name())
        for name, dat in dates:
            outv = ""
            for act in acts:
                p_e, dps = act
                sec = (dat - p_e.retrieved_at).total_seconds()
                health_value = round(
                    ((p_e.health + (dps * sec)) / p_e.maxHealth) * 100.0, 4
                )
                if 0.0 < health_value < 100.0:
                    outv += f"\n* {p_e.get_name()}: `{health_value}`"
            output_list.append((name, prioritized_string_split(outv, ["\n"])))

        return output_list

    def get_planet_fronts(self, planet: Planet) -> List[str]:
        """Get the "front" of the planet.  The front is all factions connected to it via
        warp link."""
        results = self.depth_first_planet_search(planet)

        fronts = set()
        for index in results:
            planet = self.planets.get(index, None)
            if planet:
                fronts.add(planet.currentOwner.upper())

        return list(fronts)

    def depth_first_planet_search(self, planet: Planet) -> int:
        visited = set()
        stack = [planet.index]

        result = []

        while stack:
            planet_ind = stack.pop()
            planet = self.planets.get(planet_ind, None)
            if not planet:
                continue
            if planet.index not in visited:
                # fronts.add(planet.currentOwner.upper())
                visited.add(planet.index)
                result.append(planet.index)
                for neighbor_index in planet.waypoints:
                    if neighbor_index not in visited:
                        stack.append(neighbor_index)
                for k, p in self.planets.items():
                    if planet_ind in p.waypoints:
                        if k not in visited:
                            stack.append(planet_ind)
        return result

    def calculate_total_impact(self):
        all_players, last = self.war.get_first_change()
        total_contrib = [0, 0.0, 0.0, 0.0, 0.0]
        for k, list in self.campaigns.items():
            camp, last = list.get_first_change()
            if camp.planet is None:
                continue
            if camp.planet.statistics is None:
                continue
            pc = camp.planet.statistics.playerCount
            planet_difference: Planet = (camp - last).planet
            if planet_difference.event != None:
                p_evt = planet_difference.event
                if isinstance(p_evt.time_delta, datetime.timedelta):
                    total_sec = p_evt.time_delta.total_seconds()
                    if total_sec == 0:
                        continue
                    rate = -1 * (p_evt.health)
                    total_contrib[0] += camp.planet.statistics.playerCount
                    total_contrib[1] += rate

                    total_contrib[4] += rate / total_sec

            elif planet_difference.health_percent() != 0:
                if isinstance(planet_difference.time_delta, datetime.timedelta):
                    total_sec = planet_difference.time_delta.total_seconds()
                    if total_sec == 0:
                        continue
                    rate = (-1 * (planet_difference.health)) + (
                        (camp.planet.regenPerSecond) * total_sec
                    )
                    total_contrib[0] += camp.planet.statistics.playerCount
                    total_contrib[1] += rate

                    total_contrib[4] += rate / total_sec

        diver_amount = total_contrib[0]
        total_players = all_players.statistics.playerCount
        diverpercent = round((total_contrib[0] / total_players) * 100.0, 4)
        total_contrib2 = round(total_contrib[1], 4)
        per_second = round(total_contrib[4], 8)

        return diver_amount, total_players, diverpercent, total_contrib2, per_second


def save_to_json(api_status: "ApiStatus", filepath: str) -> None:
    """
    Save the given api_status to a JSON file.

    Args:
        api_status (ApiStatus): The API status object to be saved.
        filepath (str): The path to the file where data should be saved.
    """
    with open(filepath, "w", encoding="utf8") as file:
        json.dump(api_status, file, default=str, indent=4)


def load_from_json(filepath: str) -> "ApiStatus":
    """
    Load API status data from a JSON file.

    Args:
        filepath (str): The path to the file from which data should be loaded.

    Returns:
        ApiStatus: The API status object if the file exists and is valid, otherwise None.
    """
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf8") as file:
            data = json.load(file)
    except Exception:
        # print(e)
        return None
    return data


faction_map = {
    "humans": 1,
    "terminids": 2,
    "automaton": 3,
    "illuminate": 4,
}

biome_map = {
    "unknown": 0,
    "rainforest": 1,
    "ethereal": 2,
    "jungle": 3,
    "moon": 4,
    "desert": 5,
    "winter": 6,
    "highlands": 7,
    "icemoss": 8,
    "icemoss_special": 9,
    "tundra": 10,
    "supercolony": 11,
    "blackhole": 12,
    "wasteland": 13,
    "swamp": 14,
    "desolate": 15,
    "crimsonmoor": 16,
    "canyon": 17,
    "mesa": 18,
    "toxic": 19,
    "haunted_swamp": 20,
}


def add_to_csv(stat: ApiStatus):
    """Add the data from the last period of time to the csv file."""
    # Get the first change in the war statistics
    # print(type(stat), stat.war)
    war, lastwar = stat.war.get_first_change()
    mp_mult = (war.impactMultiplier + lastwar.impactMultiplier) / 2
    all_players = war.statistics.playerCount

    # Prepare a list to hold the rows to be written to the CSV
    rows = []
    rows_for_new = []
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    timestamp = int(now.timestamp())

    # Iterate through the campaigns to gather statistics
    for k, campaign_list in stat.campaigns.items():
        if len(campaign_list) <= 1:
            # print(f"{timestamp} {k} not enough campaigns.")
            continue

        camp, last = campaign_list.get_change_from(15)
        # print(camp,last)
        if camp.planet is None:
            continue
        players = camp.planet.statistics.playerCount
        lastplayers = last.planet.statistics.playerCount
        avg_players = (players + lastplayers) / 2

        change = camp - last
        decay = camp.planet.regenPerSecond
        # total_sec = change.planet
        total_sec = change.time_delta.total_seconds()
        if total_sec <= 0:
            continue
        damage = (change.planet.health / total_sec) * -1
        evt_damage = None
        mode = 1
        owner = camp.planet.currentOwner.lower()
        attacker = "humans"
        if change.planet.event:
            evt_damage = (change.planet.event.health / total_sec) * -1
            attacker = change.planet.event.faction.lower()
        if damage == 0:
            eps = 0
            if evt_damage:
                if evt_damage <= 0:
                    # print("Event Damage too low!")
                    continue
                else:
                    mode = 2
                    eps = (evt_damage) / mp_mult
                    decay = 0
            else:
                continue
        else:
            eps = (damage + decay) / mp_mult

        stats = change.planet.statistics
        wins = stats.missionsWon / total_sec
        loss = stats.missionsLost / total_sec
        kills = (
            stats.automatonKills + stats.terminidKills + stats.illuminateKills
        ) / total_sec
        deaths = stats.deaths / total_sec

        planet = change.planet
        central = stat.statics.galaxystatic["planets"].get((planet.index), None)
        biome = "unknown"
        hazards = ""
        if central:
            bname = central["biome"]
            if bname:
                biome = bname

        row = {
            "timestamp": timestamp,
            "player_count": players,
            "mode": mode,
            "mp_mult": war.impactMultiplier,
            "wins_per_sec": wins,
            "loss_per_sec": loss,
            "decay_rate": decay,
            "kills_per_sec": kills,
            "deaths_per_sec": deaths,
            "eps": eps,
        }

        row2 = {
            "timestamp": timestamp,
            "player_count": players,
            "all_players": all_players,
            "mode": mode,
            "mp_mult": war.impactMultiplier,
            "wins_per_sec": wins,
            "loss_per_sec": loss,
            "decay_rate": decay,
            "kills_per_sec": kills,
            "deaths_per_sec": deaths,
            "eps": eps,
            "cid": change.id,
            "pid": change.planet.index,
            "biomeid": biome_map.get(biome, 0),
            "dow": now.weekday() + 1,
            "hour": now.hour + 1,
            "owner": faction_map.get(owner, 4),
            "attacker": faction_map.get(attacker, 4),
        }

        # Append the row to the list of rows
        rows.append(row)
        rows_for_new.append(row2)

    # Define the CSV file path
    csv_newfile_path = "statistics_newer.csv"
    csv_file_path = "statistics.csv"
    csv_impact_track = "impact_track.csv"

    csv_funnynumber = "funny_number_track.csv"

    diver_amount, total_players, diverpercent, total_contrib, per_second = (
        stat.calculate_total_impact()
    )
    rows_for_imp = [
        {
            "timestamp": timestamp,
            "players_contriv": diver_amount,
            "total_players": total_players,
            "player_percent": diverpercent,
            "total_contrib": total_contrib,
            "per_second": per_second,
        }
    ]
    rows_for_number = []
    for i in stat.warall.status.globalResources:
        rows_for_number.append(
            {
                "timestamp": timestamp,
                "id": i.id32,
                "value": i.currentValue,
                "maxValue": i.maxValue,
            }
        )

    with open(csv_impact_track, mode="a+", newline="", encoding="utf8") as file:
        writer = csv.DictWriter(file, fieldnames=rows_for_imp[0].keys())

        # If the file is empty, write the header
        if file.tell() == 0:
            writer.writeheader()

        # Write the rows
        for row in rows_for_imp:
            writer.writerow(row)
    # Write the rows to the CSV file
    # print(rows)
    if not rows:
        return
    with open(csv_file_path, mode="a", newline="", encoding="utf8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())

        # If the file is empty, write the header
        if file.tell() == 0:
            writer.writeheader()

        # Write the rows
        for row in rows:
            writer.writerow(row)

    with open(csv_newfile_path, mode="a", newline="", encoding="utf8") as file:
        writer = csv.DictWriter(file, fieldnames=rows_for_new[0].keys())

        # If the file is empty, write the header
        if file.tell() == 0:
            writer.writeheader()

        # Write the rows
        for row in rows_for_new:
            writer.writerow(row)


def get_feature_dictionary(
    stat: ApiStatus, camp_key: Any
) -> Dict[str, Union[int, float]]:
    """
    Create a feature dictionary for predicting Exp Per Second
    """
    war = stat.war.get_first()
    mp_mult = war.impactMultiplier
    campaign_list = stat.campaigns[camp_key]
    camp, last = campaign_list.get_first_change()
    players = camp.planet.statistics.playerCount

    change = camp - last
    decay = camp.planet.regenPerSecond
    total_sec = change.planet.time_delta.total_seconds()
    if total_sec == 0:
        total_sec = 1
    damage = (change.planet.health / total_sec) * -1
    evt_damage = None
    mode = 1
    if change.planet.event:
        evt_damage = (change.planet.event.health / total_sec) * -1
    if damage == 0:
        eps = 0
        if evt_damage:
            if evt_damage <= 0:
                print("Event Damage too low!")
            else:
                mode = 2
                eps = (evt_damage) / mp_mult
                decay = 0
    else:
        eps = (damage + decay) / mp_mult

    stats = change.planet.statistics
    wins = stats.missionsWon / total_sec
    loss = stats.missionsLost / total_sec
    kills = (
        stats.automatonKills + stats.terminidKills + stats.illuminateKills
    ) / total_sec
    deaths = stats.deaths / total_sec
    row = {
        "timestamp": int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp()),
        "player_count": players,
        "mode": mode,
        "mp_mult": mp_mult,
        "wins_per_sec": wins,
        "loss_per_sec": loss,
        "decay_rate": decay,
        "kills_per_sec": kills,
        "deaths_per_sec": deaths,
        "eps": eps,
    }
    return row


def write_statistics_to_csv(stats: ApiStatus):
    """dump planet statistics at current time to csv file."""
    headers = [
        "planet_name",
        "sector_name",
        "front",
        "current_owner",
        "missionsWon",
        "missionsLost",
        "kills",
        "deaths",
        "friendlies",
        "DPM",
        "KPM",
        "KTD",
        "WTL",
        "biome",
        "hazards",
        "MSR",
        "missionTime",
        "timePerMission",
        "timePlayed",
        "timePlayedPerMission",
        "bulletsFired",
        "bulletsHit",
        "accuracy",
        "bug_kills",
        "bot_kills",
        "squid_kills",
        "initial_owner",
        "revives",
        "playerCount",
    ]
    csv_file_path = "statistics_sub.csv"
    # Open the CSV file for writing
    with open(csv_file_path, mode="w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=headers)

        # Write the header
        writer.writeheader()

        # Write each statistics entry
        for _, planet in stats.planets.items():
            stat = planet.statistics
            missions = max(stat.missionsWon + stat.missionsLost, 1)

            central = stats.statics.galaxystatic["planets"].get(int(planet.index), None)
            biome = "unknown"
            hazards = ""
            if central:
                bname = central["biome"]
                bhazard = central["environmentals"]
                planet_biome = stats.statics.galaxystatic["biomes"].get(bname, None)
                planet_hazards = [
                    stats.statics.galaxystatic["environmentals"].get(h, None)
                    for h in bhazard
                ]
                if planet_biome:
                    biome_name = planet_biome.get("name", "[GWW SEARCH ERROR]")
                    biome_description = planet_biome.get(
                        "description", "No description available"
                    )
                    biome = biome_name

                if planet_hazards:
                    hazards_str = []
                    for hazard in planet_hazards:
                        hazard_name = hazard.get("name", "Unknown Hazard")
                        hazard_description = hazard.get(
                            "description", "No description available"
                        )
                        hazards_str.append(f"{hazard_name}")
                    hazards = ",".join(h for h in hazards_str)

            kills = stat.terminidKills + stat.automatonKills + stat.illuminateKills
            thistime = round(max(stat.missionTime, 1) / (missions), 4)
            front = stats.get_planet_fronts(planet)
            # print(front)
            if "HUMANS" in front and len(front) > 1:
                front.remove("HUMANS")
            row = {
                "planet_name": planet.name,
                "sector_name": planet.sector.upper(),
                "front": ",".join(f for f in front),
                "initial_owner": planet.initialOwner,
                "current_owner": planet.currentOwner,
                "missionsWon": stat.missionsWon,
                "missionsLost": stat.missionsLost,
                "missionTime": stat.missionTime,
                "timePerMission": thistime,
                "kills": kills,
                "bug_kills": stat.terminidKills,
                "bot_kills": stat.automatonKills,
                "squid_kills": stat.illuminateKills,
                "bulletsFired": stat.bulletsFired,
                "bulletsHit": stat.bulletsHit,
                "timePlayed": stat.timePlayed,
                "timePlayedPerMission": (stat.timePlayed / missions),
                "deaths": stat.deaths,
                "revives": stat.revives,
                "friendlies": stat.friendlies,
                "MSR": stat.missionSuccessRate,
                "accuracy": stat.accuracy,
                "DPM": stat.deaths / missions,
                "KPM": kills / missions,
                "KTD": kills / max(stat.deaths, 1),
                "WTL": stat.missionsWon / max(stat.missionsLost, 1),
                "biome": biome,
                "hazards": hazards,
                "playerCount": stat.playerCount,
            }
            writer.writerow(row)
