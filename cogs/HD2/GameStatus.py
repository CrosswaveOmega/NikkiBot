import csv
import datetime
import json

import numpy as np

from .helldive import *
from utility import prioritized_string_split


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
        }

    @classmethod
    def from_dict(cls, data, client: APIConfig = APIConfig()):
        print(data)
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
            print(newcks.campaigns)
        newcks.planets = {int(k): Planet(**v) for k, v in data["planets"].items()}
        newcks.dispatches = [Dispatch(**d) for d in data["dispatches"]]
        return newcks

    def __repr__(self):
        s = ""
        s += repr(self.war) + "\n"
        s += repr(self.assignments) + "\n"
        s += repr(self.campaigns) + "\n"
        # s+=repr(self.dispatches )+"\n"
        # s+=repr(self.planets)
        return s

    async def update_data(self):
        """
        Query the community api, and load the data into the classes.
        """
        print(self.client)
        war = None
        campaigns = None
        assignments = None
        dispatches = None
        try:
            war = await GetApiV1War(api_config_override=self.client)
            assignments = await GetApiV1AssignmentsAll(api_config_override=self.client)
            campaigns = await GetApiV1CampaignsAll(api_config_override=self.client)
            dispatches = await GetApiV1DispatchesAll(api_config_override=self.client)
        except Exception as e:
            raise e

        if dispatches is not None:
            self.dispatches = dispatches

        if war is not None:
            self.war.add(war)

        self.handle_data(assignments, self.assignments, "assignment")
        self.handle_data(campaigns, self.campaigns, "campaign")

        if datetime.datetime.now() >= self.last_planet_get + datetime.timedelta(
            hours=2
        ):
            planets = await GetApiV1PlanetsAll()
            planet_data = {}
            for planet in planets:
                planet_data[planet.index] = planet
            self.planets = planet_data
            self.last_planet_get = datetime.datetime.now()

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
            data_ids = set()
            data_ids: Set[int] = set()
            for item in data:
                data_ids.add(item.id)
                if item.id not in storage:
                    storage[item.id] = LimitedSizeList(self.max_list_size)
                storage[item.id].add(item)
            key_list = list(storage.keys())
            for k in key_list:
                if k not in data_ids:
                    print(f"removing {data_type} {k}")
                    storage.pop(k)

    def estimates(self):
        acts: List[Tuple[Union[Planet, Event], float]] = []
        dates: List[datetime.datetime] = []
        outv: str = ""
        # Get all planets and Events out of the current list of campaigns.

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
                    planet.event
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
                if health_value < 100.0 and health_value > 0.0:
                    outv += f"\n* {p_e.get_name()}: `{health_value}`"
            output_list.append((name, prioritized_string_split(outv, ["\n"])))

        return output_list


def save_to_json(api_status, filepath):
    with open(filepath, "w", encoding="utf8") as file:
        json.dump(api_status.to_dict(), file, default=str, indent=4)


def load_from_json(filepath):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf8") as file:
            data = json.load(file)
    except Exception as e:
        return None
    return data


def add_to_csv(stat: ApiStatus):
    """Add the data from the last period of time to the csv file."""
    # Get the first change in the war statistics
    print(type(stat), stat.war)
    war = stat.war.get_first()
    mp_mult = war.impactMultiplier

    # Prepare a list to hold the rows to be written to the CSV
    rows = []
    timestamp = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
    # Iterate through the campaigns to gather statistics
    for k, campaign_list in stat.campaigns.items():
        if len(campaign_list) <= 1:
            print(f"{timestamp} {k} not enough campaigns.")
            continue

        camp, last = campaign_list.get_first_change()
        players = camp.planet.statistics.playerCount

        change = camp - last
        decay = camp.planet.regenPerSecond
        total_sec = change.planet.retrieved_at.total_seconds()
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

        # Prepare the row for the CSV
        row = {
            "timestamp": timestamp,
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

        # Append the row to the list of rows
        rows.append(row)

    # Define the CSV file path
    csv_file_path = "statistics.csv"

    # Write the rows to the CSV file
    print(rows)
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
