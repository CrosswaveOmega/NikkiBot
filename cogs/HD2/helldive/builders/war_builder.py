from typing import List, Optional, Type, TypeVar, Dict

import httpx

import datetime as dt
from ..api_config import APIConfig, HTTPException
from ..models import *
from ..models.ABC.model import BaseApiModel

from hd2json.jsonutils import load_and_merge_json_files
from ..constants import task_types, value_types, faction_names, samples

from .effect_builder import build_planet_effect

from .planet_builder import get_time




def build_war(diveharder: DiveharderAll)->War:
    info=diveharder.war_info
    stats=diveharder.planet_stats.galaxy_stats

    player_count=sum(st.players for st in diveharder.status.planetStatus if st.players is not None)


    stats_build = Statistics(
        retrieved_at=stats.retrieved_at,
        playerCount=player_count,
        missionsWon=stats.missionsWon,
        missionsLost=stats.missionsLost,
        missionTime=stats.missionTime,
        terminidKills=stats.bugKills,
        automatonKills=stats.automatonKills,
        illuminateKills=stats.illuminateKills,
        bulletsFired=stats.bulletsFired,
        bulletsHit=stats.bulletsHit,
        timePlayed=stats.timePlayed,
        deaths=stats.deaths,
        revives=stats.revives,
        friendlies=stats.friendlies,
        missionSuccessRate=stats.missionSuccessRate,
        accuracy=stats.accurracy,
    )
    war=War(
        retrieved_at=diveharder.status.retrieved_at,
        warId=diveharder.status.warId,
        started=(dt.datetime.fromtimestamp(info.startDate,tz=dt.timezone.utc)).isoformat(),
        ended=(dt.datetime.fromtimestamp(info.endDate,tz=dt.timezone.utc)).isoformat(),
        clientVersion=info.minimumClientVersion,
        now=info.retrieved_at.isoformat(),
        impactMultiplier=diveharder.status.impactMultiplier,
        factions=['Humans', 'Terminids', 'Automaton', 'Illuminate'],
        statistics=stats_build,
    )
    return war
