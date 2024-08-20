import asyncio
import csv
import datetime
import json

import numpy as np

from hd2json.jsonutils import load_and_merge_json_files

from .diff_util import detect_loggable_changes
from .helldive import *
from .utils import prioritized_string_split

MAX_ATTEMPT = 3


class LimitedSizeList(list):
    """A list that can only have a fixed amount of elements."""

    def __init__(self, max_size):
        self.max_size = max_size
        self.items: List[Union[War, Assignment2, Campaign2]] = []

    def add(self, item):
        if len(self.items) >= self.max_size:
            self.items.pop()
        self.items.insert(0, item)

    def push(self, item):
        if len(self.items) >= self.max_size:
            self.items.pop(0)
        self.items.append(item)

    def get_changes(self) -> List[Union[War, Assignment2, Campaign2]]:
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
        return self.items[0], self.items[0]

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
        "planets",
        "dispatches",
        "last_planet_get",
        "planetdata",
        "warall",
        "nowval",
    ]

    def __init__(self, client: APIConfig = APIConfig(), max_list_size=8):
        self.client = client
        self.max_list_size = max_list_size
        self.war: LimitedSizeList[War] = LimitedSizeList(self.max_list_size)
        self.assignments: Dict[int, LimitedSizeList[Assignment2]] = {}
        self.campaigns: Dict[int, LimitedSizeList[Campaign2]] = {}
        self.planets: Dict[int, Planet] = {}
        self.dispatches: List[Dispatch] = []
        self.last_planet_get: datetime.datetime = datetime.datetime(2024, 1, 1, 0, 0, 0)
        self.warall: DiveharderAll = None
        self.nowval = DiveharderAll(status=WarStatus(), war_info=WarInfo())
        planetjson = load_and_merge_json_files("./hd2json/planets")
        self.planetdata: Dict[str, Any] = GalaxyStatic(**planetjson)

    def to_dict(self):
        return {
            "max_list_size": self.max_list_size,
            "war": [w.model_dump() for w in self.war.items],
            "assignments": {
                k: [item.model_dump() for item in v.items]
                for k, v in self.assignments.items()
            },
            "campaigns": {
                k: [item.model_dump() for item in v.items]
                for k, v in self.campaigns.items()
            },
            "planets": {k: p.model_dump() for k, p in self.planets.items()},
            "dispatches": [d.model_dump() for d in self.dispatches],
            # "warstat": self.warstat.model_dump(),
            "warall": self.warall.model_dump(),
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
            # print(newcks.campaigns)
        newcks.planets = {int(k): Planet(**v) for k, v in data["planets"].items()}
        newcks.dispatches = [Dispatch(**d) for d in data["dispatches"]]
        if "warstat" in data:
            newcks.warstat = WarStatus(**data["warstat"])
        if "warall" in data:
            newcks.warall = DiveharderAll(**data["warall"])
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
        self, current, Queue: asyncio.Queue, nowval=None
    ) -> Tuple[Dict[str, Dict[str, Union[List, Dict[str, Any]]]], DiveharderAll]:

        if nowval:
            nowv = nowval
        else:
            nowv = await GetApiRawAll(api_config_override=self.client)
        self.warall = nowv
        if nowv:
            if current:
                diff = await detect_loggable_changes(current, nowv, Queue)
                return diff, nowv

        return None, nowv

    async def update_data(self):
        """
        Query the community api, and load the data into the classes.
        """
        # print(self.client)
        war = None
        campaigns = None
        assignments = None
        dispatches = None
        maxattempt = 3
        try:
            attempt_count = 0
            while attempt_count < maxattempt:
                try:
                    war = await GetApiV1War(api_config_override=self.client)
                    break
                except Exception as e:
                    attempt_count += 1
                    await asyncio.sleep(2)
                    if attempt_count >= maxattempt:
                        raise e
            attempt_count = 0
            while attempt_count < maxattempt:
                try:
                    as1 = await GetApiV1AssignmentsAll(api_config_override=self.client)
                    assignments = []
                    for a in as1:
                        for m in self.warall.major_order:
                            print(m.id32)
                            if m.id32 == a.id:
                                a.rewards = m.setting.rewards
                        assignments.append(a)
                    break
                except Exception as e:
                    attempt_count += 1

                    await asyncio.sleep(2)
                    if attempt_count >= maxattempt:
                        raise e
            attempt_count = 0
            while attempt_count < maxattempt:
                try:
                    campaigns = await GetApiV1CampaignsAll(
                        api_config_override=self.client
                    )
                    break
                except Exception as e:
                    attempt_count += 1

                    await asyncio.sleep(2)
                    if attempt_count >= maxattempt:
                        raise e

        except Exception as e:
            raise e

        # print(war, campaigns, assignments)
        if war is not None:
            self.war.add(war)

        self.handle_data(assignments, self.assignments, "assignment")
        self.handle_data(campaigns, self.campaigns, "campaign")
        for l in self.campaigns.values():
            camp = l.get_first()
            self.planets[camp.planet.index] = camp.planet
        if datetime.datetime.now() >= self.last_planet_get + datetime.timedelta(
            hours=2
        ):
            planets = await GetApiV1PlanetsAll(api_config_override=self.client)
            planet_data = {}
            for planet in planets:
                planet_data[planet.index] = planet
            self.planets = planet_data
            self.last_planet_get = datetime.datetime.now()
        else:
            dispatches = await GetApiV1DispatchesAll(api_config_override=self.client)
            if dispatches is not None:
                self.dispatches = dispatches

            # print(self.warstat)

    def handle_data(
        self,
        data: List[Union[Campaign2, Assignment2]],
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
                    # print(f"removing {data_type} {k}")
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
                    f"{camp.title}:End at{fdt(et(camp.expiration),'R')}",
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
                        f"{camp.planet.get_name()}:{camp.planet.format_estimated_time_string(dps,proj_date)}",
                        proj_date,
                    )
                )
            if eps != 0:
                proj_date = camp.planet.event.calculate_timeval(eps, eps > 0)
                acts.append((camp.planet.event, eps))
                dates.append(
                    (
                        f"{camp.planet.get_name()}:{camp.planet.event.format_estimated_time_string(eps,proj_date)}",
                        proj_date,
                    )
                )
                dates.append(
                    (
                        f"{camp.planet.get_name()}:End at{fdt(et(camp.planet.event.endTime),'R')}",
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


def save_to_json(api_status: "ApiStatus", filepath: str) -> None:
    """
    Save the given api_status to a JSON file.

    Args:
        api_status (ApiStatus): The API status object to be saved.
        filepath (str): The path to the file where data should be saved.
    """
    with open(filepath, "w", encoding="utf8") as file:
        json.dump(api_status.to_dict(), file, default=str, indent=4)


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
    except Exception as e:
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
    "swamp": 13,
    "rainyjungle": 14,
    "desolate": 15,
    "crimsonmoor": 16,
    "canyon": 17,
    "mesa": 18,
    "toxic": 19,
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

        camp, last = campaign_list.get_first_change()
        players = camp.planet.statistics.playerCount
        lastplayers = last.planet.statistics.playerCount
        avg_players = (players + lastplayers) / 2

        change = camp - last
        decay = camp.planet.regenPerSecond
        total_sec = change.planet.retrieved_at.total_seconds()
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
        central = stat.planetdata["planets"].get(str(planet.index), None)
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
    total_sec = change.planet.retrieved_at.total_seconds()
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

            central = stats.planetdata["planets"].get(str(planet.index), None)
            biome = "unknown"
            hazards = ""
            if central:
                bname = central["biome"]
                bhazard = central["environmentals"]
                planet_biome = stats.planetdata["biomes"].get(bname, None)
                planet_hazards = [
                    stats.planetdata["environmentals"].get(h, None) for h in bhazard
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
