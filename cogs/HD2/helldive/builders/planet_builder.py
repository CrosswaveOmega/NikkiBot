from typing import List, Optional, Type, TypeVar, Dict

import httpx

import datetime as dt
from ..api_config import APIConfig, HTTPException
from ..models import *
from ..models.ABC.model import BaseApiModel

from ..constants import task_types, value_types, faction_names, samples


def check_compare_value(key, value, target: List[Dict[str, Any]]):
    for s in target:
        if s[key] == value:
            return s
    return None


def get_time(diveharder: DiveharderAll) -> dt.datetime:
    status = diveharder.status
    info = diveharder.war_info

    # Get datetime diveharder object was retrieved at
    now = diveharder.retrieved_at
    gametime = dt.datetime.fromtimestamp(
        info.startDate, tz=dt.timezone.utc
    ) + dt.timedelta(seconds=status.time)
    deviation = now - gametime
    print(deviation)
    relative_game_start = (
        dt.datetime.fromtimestamp(info.startDate, tz=dt.timezone.utc) + deviation
    )
    return relative_game_start


async def build_planet_2(
    planetIndex, diveharder: DiveharderAll, planetdata: GalaxyStatic
):
    status = diveharder.status
    info = diveharder.war_info
    stat = diveharder.planet_stats.planets_stats

    planetStatus = check_compare_value("index", planetIndex, status.planetStatus)
    planetInfo = check_compare_value("index", planetIndex, info.planetInfos)
    planetStat = check_compare_value("planetIndex", planetIndex, stat)

    planet = planetdata.build_planet(planetIndex, planetStatus, planetInfo, planetStat)

    event = check_compare_value("planetIndex", planetIndex, status.planetEvents)
    starttime = get_time(diveharder)
    if event:
        newevent = Event(
            id=event.id,
            eventType=event.eventType,
            faction=faction_names.get(event.race, "???"),
            health=event.health,
            maxHealth=event.maxHealth,
            startTime=starttime + (dt.timedelta(seconds=event.startTime)),
            endTime=starttime + (dt.timedelta(seconds=event.endTime)),
            campaignId=event.campaignId,
            jointOperationIds=event.jointOperationIds,
        )
        planet.event = newevent
    return planet
    pass
