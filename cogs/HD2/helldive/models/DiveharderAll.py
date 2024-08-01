from typing import *

import logging

logs = logging.getLogger("TCLogger")

from pydantic import Field
from .ABC.model import BaseApiModel
import discord
import asyncio

from .WarStatus import WarStatus
from .WarInfo import WarInfo
from .WarSummary import WarSummary
from .Assignment import Assignment
from .NewsFeedItem import NewsFeedItem
from .SteamNews import SteamNewsRaw
from .WarId import WarId


class DiveharderAll(BaseApiModel):
    """
    None model
        A message from high command to the players, usually updates on the status of the war effort.

    """

    status: Optional[WarStatus] = Field(alias="status", default=None)

    war_info: Optional[WarInfo] = Field(alias="war_info", default=None)

    planet_stats: Optional[WarSummary] = Field(alias="planet_stats", default=None)

    major_order: Optional[List[Assignment]] = Field(alias="major_order", default=None)

    personal_order: Optional[List[Assignment]] = Field(
        alias="personal_order", default=None
    )

    news_feed: Optional[List[NewsFeedItem]] = Field(alias="news_feed", default=None)

    updates: Optional[List[SteamNewsRaw]] = Field(alias="updates", default=None)

    war_id: Optional[WarId] = Field(alias="war_id", default=None)


async def compare_value_with_timeout(model1, field):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(model1.get, field, None), timeout=5
        )
    except asyncio.TimeoutError as e:
        logs.error("Could not get field %s ", field, exc_info=e)
        raise e


async def get_differing_fields(
    model1: BaseApiModel, model2: BaseApiModel, lvd=0, to_ignore=[]
) -> dict:
    if type(model1) is not type(model2):
        raise ValueError("Both models must be of the same type")

    differing_fields = {}
    to_ignore.append("retrieved_at")
    to_ignore.append("self")
    if lvd > 20:
        return "ERROR"

    async def compare_values(val1, val2):
        if isinstance(val1, BaseApiModel) and isinstance(val2, BaseApiModel):
            return await get_differing_fields(val1, val2, lvd + 1)
        elif isinstance(val1, list) and isinstance(val2, list):
            list_diffs = {}
            if len(val1) != len(val2):
                # print(len(val1),len(val2))
                biggestsize = max(len(val1), len(val2))
                for i in range(biggestsize):
                    v1 = val1[i] if i < len(val1) else None
                    v2 = val2[i] if i < len(val2) else None
                    if isinstance(v1, BaseApiModel) and isinstance(v2, BaseApiModel):
                        differing = await get_differing_fields(v1, v2, lvd + 1)
                        if differing:
                            list_diffs[i] = differing
                    elif str(v1) != str(v2):
                        target = {}
                        target = {
                            k: v
                            for k, v in zip(["old", "new"], [v1, v2])
                            if v is not None
                        }
                        if target:
                            list_diffs[i] = target
            else:
                for i, (v1, v2) in enumerate(zip(val1, val2)):
                    if isinstance(v1, BaseApiModel) and isinstance(v2, BaseApiModel):
                        differing = await get_differing_fields(v1, v2, lvd + 1)
                        if differing:
                            list_diffs[i] = differing
                    elif str(v1) != str(v2):
                        list_diffs[i] = {"old": v1, "new": v2}

            return list_diffs if list_diffs else None
        else:

            return str(val1) != str(val2)

    for field in model1.model_fields:
        if field not in to_ignore:
            logs.info("Retrieving field %s ", field)
            value1 = await compare_value_with_timeout(model1, field)
            value2 = await compare_value_with_timeout(model2, field)

            diffs = await compare_values(value1, value2)
            if isinstance(diffs, dict):
                if diffs:
                    differing_fields[field] = diffs
            elif not diffs:
                continue
            else:
                if value1 == value2:
                    continue
                differing_fields[field] = {"old": value1, "new": value2}

    return differing_fields


async def check_compare_value(key, value, target: List[Dict[str, Any]]):
    for s in target:
        if s[key] == value:
            return s
    return None


async def check_compare_value_list(
    keys: List[str], values: List[Any], target: List[Dict[str, Any]]
):
    for s in target:
        if all(s[key] == value for key, value in zip(keys, values)):
            return s
    return None


async def process_planet_events(
    source, target, place, key, QueueAll, batch, exclude=[]
):
    pushed_items = []
    for event in source:
        oc = await check_compare_value(key, event[key], target)
        if not oc:
            item = {
                "mode": "new",
                "place": place,
                "batch": batch,
                "value": event,
            }
            pushed_items.append(item)
            await QueueAll.put(item)
        else:
            differ = await get_differing_fields(oc, event, to_ignore=exclude)
            if differ:
                item = {
                    "mode": "change",
                    "place": place,
                    "batch": batch,
                    "value": (event, differ),
                }
                pushed_items.append(item)
                await QueueAll.put(item)

    for event in target:
        if not await check_compare_value(key, event[key], source):
            item = {
                "mode": "remove",
                "place": place,
                "batch": batch,
                "value": event,
            }
            pushed_items.append(item)
            await QueueAll.put(item)

    return pushed_items


async def process_planet_attacks(
    source, target, place, keys, QueueAll, batch, exclude=[]
):
    pushed_items = []
    for event in source:
        oc = await check_compare_value_list(keys, [event[key] for key in keys], target)
        if not oc:
            print(place, "new", event)
            item = {
                "mode": "new",
                "place": place,
                "batch": batch,
                "value": event,
            }
            pushed_items.append(item)
            await QueueAll.put(item)

    for event in target:
        if not await check_compare_value_list(
            keys, [event[key] for key in keys], source
        ):
            item = {
                "mode": "remove",
                "place": place,
                "batch": batch,
                "value": event,
            }
            pushed_items.append(item)
            await QueueAll.put(item)

    return pushed_items


async def detect_loggable_changes(
    old: BaseApiModel, new: BaseApiModel, QueueAll: asyncio.Queue
) -> Tuple[dict, list]:
    out = {
        "campaign": {"new": {}, "changes": {}, "old": {}},
        "planetevents": {"new": {}, "changes": {}, "old": {}},
        "planets": {"new": {}, "changes": {}, "old": {}},
        "planetAttacks": {"new": {}, "changes": {}, "old": {}},
        "planetInfo": {"new": {}, "changes": {}, "old": {}},
        "globalEvents": {"new": {}, "changes": {}, "old": {}},
        "sectors": {"new": {}, "changes": {}, "old": {}},
        "news": {"new": {}, "changes": {}, "old": {}},
        "stats_raw": {"changes": {}},
        "info_raw": {"changes": {}},
    }
    batch = int(new.retrieved_at.timestamp())
    superlist = []

    rawout = await get_differing_fields(
        old.status,
        new.status,
        to_ignore=[
            "time",
            "planetAttacks",
            "impactMultiplier",
            "campaigns",
            "planetStatus",
            "planetEvents",
            "globalEvents",
        ],
    )
    if rawout:
        item = {
            "mode": "change",
            "place": "stats_raw",
            "batch": batch,
            "value": (new.status, rawout),
        }
        superlist.append(item)
        await QueueAll.put(item)
    out["stats_raw"]["changes"] = rawout
    logs.info("Starting loggable detection, stand by...")
    superlist += await process_planet_attacks(
        new.status.planetAttacks,
        old.status.planetAttacks,
        "planetAttacks",
        ["source", "target"],
        QueueAll,
        batch,
    )

    infoout = await get_differing_fields(
        old.war_info, new.war_info, to_ignore=["planetInfos"]
    )
    if infoout:
        item = {
            "mode": "change",
            "place": "info_raw",
            "batch": batch,
            "value": (new.war_info, infoout),
        }
        superlist.append(item)
        await QueueAll.put(item)
    logs.info("News feed loggable detection, stand by...")
    superlist += await process_planet_events(
        new.news_feed, old.news_feed, "news", "id", QueueAll, batch
    )

    logs.info("campaigns detection, stand by...")
    superlist += await process_planet_events(
        new.status.campaigns, old.status.campaigns, "campaign", "id", QueueAll, batch
    )
    logs.info("planet events detection, stand by...")
    superlist += await process_planet_events(
        new.status.planetEvents,
        old.status.planetEvents,
        "planetevents",
        "id",
        QueueAll,
        batch,
    )
    logs.info("planet status detection, stand by...")
    superlist += await process_planet_events(
        new.status.planetStatus,
        old.status.planetStatus,
        "planets",
        "index",
        QueueAll,
        batch,
        ["health", "players"],
    )
    logs.info("global event detection, stand by...")
    superlist += await process_planet_events(
        new.status.globalEvents,
        old.status.globalEvents,
        "globalEvents",
        "eventId",
        QueueAll,
        batch,
    )
    logs.info("planet info detection, stand by...")
    superlist += await process_planet_events(
        new.war_info.planetInfos,
        old.war_info.planetInfos,
        "planetInfo",
        "index",
        QueueAll,
        batch,
        ["position"],
    )
    superlist += await process_planet_events(
        new.status.sector_states(),
        old.status.sector_states(),
        "sectors",
        "name",
        QueueAll,
        batch,
        ["planetStatus"],
    )
    logs.info("Done detection, stand by...")
    return superlist
