from typing import List, Optional, Type, TypeVar, Dict

import httpx

import datetime as dt
from ..api_config import APIConfig, HTTPException
from ..models import *
from ..models.ABC.model import BaseApiModel

from hd2json.jsonutils import load_and_merge_json_files
from ..constants import task_types, value_types, faction_names, samples

from .effect_builder import build_planet_effect


def check_compare_value(key, value, target: List[Dict[str, Any]]):
    for s in target:
        if s[key] == value:
            return s
    return None


def check_compare_value_list(
    keys: List[str], values: List[Any], target: List[Dict[str, Any]]
):
    values = []
    for s in target:
        if all(s[key] == value for key, value in zip(keys, values)):
            values.append(s)
    return values
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


def build_planet_2(planetIndex, diveharder: DiveharderAll, statics: StaticAll):
    status = diveharder.status
    info = diveharder.war_info
    if diveharder.planet_stats is not None:
        stat = diveharder.planet_stats.planets_stats
    # print('index is', planetIndex)
    planetStatus = check_compare_value("index", planetIndex, status.planetStatus)
    planetInfo = check_compare_value("index", planetIndex, info.planetInfos)
    if stat is not None:
        planetStat = check_compare_value("planetIndex", planetIndex, stat)
        if not planetStat:
            planetStat = PlanetStats(planetIndex=planetIndex)
    else:
        planetStat = PlanetStats(planetIndex=planetIndex)
    planet = statics.galaxystatic.build_planet(
        planetIndex, planetStatus, planetInfo, planetStat
    )
    planet.sector_id = planetInfo.sector

    planet_effect_list = []
    planet_attack_list = []
    for effect in status.planetActiveEffects:
        if effect.index == planetIndex:
            effects = build_planet_effect(statics.effectstatic, effect.galacticEffectId)
            # print(effect,effects)
            planet_effect_list.append(effects)
    for attack in status.planetAttacks:
        if attack.source == planetIndex:
            planet_attack_list.append(attack.target)

    event: PlanetEvent = check_compare_value(
        "planetIndex", planetIndex, status.planetEvents
    )
    planet.activePlanetEffects = planet_effect_list
    planet.attacking = planet_attack_list
    starttime = get_time(diveharder)
    if event:
        newevent = Event(
            retrieved_at=event.retrieved_at,
            id=event.id,
            eventType=event.eventType,
            faction=faction_names.get(event.race, "???"),
            health=event.health,
            maxHealth=event.maxHealth,
            startTime=(starttime + (dt.timedelta(seconds=event.startTime))).isoformat(),
            endTime=(starttime + (dt.timedelta(seconds=event.expireTime))).isoformat(),
            campaignId=event.campaignId,
            jointOperationIds=event.jointOperationIds,
        )
        planet.event = newevent
    return planet
    pass
