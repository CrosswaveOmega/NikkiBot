import logging
from typing import *

logs = logging.getLogger("TCLogger")

from hd2api.models.ABC.model import BaseApiModel
from hd2api.builders import *
from hd2api.models import DiveharderAll, StaticAll


from pydantic import Field
import discord
import asyncio
import random


class GameEvent(BaseApiModel):
    """
    Pydantic model for game events.

    """

    mode: Optional[str] = Field(alias="mode", default=None)

    place: Optional[str] = Field(alias="place", default=None)

    batch: Optional[int] = Field(alias="batch", default=None)

    value: Optional[Union[Any, Tuple[Any, Dict[str, Any]]]] = Field(
        alias="value", default=None
    )
    cluster: Optional[bool] = Field(alias="cluster", default=False)


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
    
    to_ignore.append("time_delta")
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
                            nt = {}
                            for m, n in target.items():
                                if isinstance(n, BaseApiModel):
                                    nt[m] = n.model_dump(exclude=["retrieved_at","time_delta"])
                                else:
                                    nt[m] = n
                            list_diffs[i] = nt
            else:
                for i, (v1, v2) in enumerate(zip(val1, val2)):
                    if isinstance(v1, BaseApiModel) and isinstance(v2, BaseApiModel):
                        differing = await get_differing_fields(v1, v2, lvd + 1)
                        if differing:
                            list_diffs[i] = differing
                    elif str(v1) != str(v2):
                        if isinstance(v1, BaseApiModel):
                            v1 = v1.model_dump(exclude=["retrieved_at","time_delta"])
                        if isinstance(v2, BaseApiModel):
                            v2 = v2.model_dump(exclude=["retrieved_at","time_delta"])
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
                if isinstance(value1, BaseApiModel):
                    value1 = value1.model_dump(exclude=["retrieved_at","time_delta"])
                if isinstance(value2, BaseApiModel):
                    value2 = value2.model_dump(exclude=["retrieved_at","time_delta"])
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
    new, old, change = [], [], []
    for event in source:
        oc = await check_compare_value(key, event[key], target)
        if not oc:
            item = GameEvent(mode="new", place=place, batch=batch, value=event)
            pushed_items.append(item)
            new.append(item)
            # await QueueAll.put(item)
        else:
            differ = await get_differing_fields(oc, event, to_ignore=exclude)
            if differ:
                item = GameEvent(
                    mode="change",
                    place=place,
                    batch=batch,
                    value=(event, differ),
                )
                pushed_items.append(item)
                change.append(item)
                # await QueueAll.put(item)

    for event in target:
        if not await check_compare_value(key, event[key], source):
            item = GameEvent(
                mode="remove",
                place=place,
                batch=batch,
                value=event,
            )
            pushed_items.append(item)
            old.append(item)
            # await QueueAll.put(item)
    if new:
        await QueueAll.put(new)

    if change:
        await QueueAll.put(change)

    if old:
        await QueueAll.put(old)
    return pushed_items


async def process_planet_attacks(
    source, target, place, keys, QueueAll, batch, exclude=[]
):
    pushed_items = []
    newlist = []
    oldlist = []
    for event in source:
        oc = await check_compare_value_list(keys, [event[key] for key in keys], target)
        if not oc:
            print(place, "new", event)
            item = GameEvent(mode="new", place=place, batch=batch, value=event)
            newlist.append(item)
            pushed_items.append(item)
            # await QueueAll.put(item)

    for event in target:
        if not await check_compare_value_list(
            keys, [event[key] for key in keys], source
        ):
            item = GameEvent(
                mode="remove",
                place=place,
                batch=batch,
                value=event,
            )
            pushed_items.append(item)
            oldlist.append(item)
            # await QueueAll.put(item)

    if place == "planetAttacks":
        if newlist:
            newitem = GameEvent(
                mode="added", place=place, batch=batch, value=newlist, cluster=True
            )
            await QueueAll.put([newitem])
        if oldlist:
            olditem = GameEvent(
                mode="removed", place=place, batch=batch, value=oldlist, cluster=True
            )
            await QueueAll.put([olditem])
    else:
        combined_list = oldlist + newlist
        await QueueAll.put(combined_list)
    return pushed_items


async def detect_loggable_changes(
    old: DiveharderAll, new: DiveharderAll, QueueAll: asyncio.Queue, statics: StaticAll
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
    batch = (int(new.retrieved_at.timestamp()) >> 4) | (random.randint(0, 15))

    superlist = []
    if old.status.time == new.status.time:
        newitem = GameEvent(
            mode="deadzone", place="deadzone", batch=batch, value=new.status
        )

        await QueueAll.put([newitem])

    rawout = await get_differing_fields(
        old.status,
        new.status,
        to_ignore=[
            "time",
            "planetAttacks",
            "impactMultiplier",
            "jointOperations",
            "campaigns",
            "planetStatus",
            "planetEvents",
            "globalEvents",
            "planetActiveEffects",
        ],
    )
    if rawout:
        item = GameEvent(
            mode="change",
            place="stats_raw",
            batch=batch,
            value=(new.status, rawout),
        )
        superlist.append(item)
        await QueueAll.put([item])
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
    superlist += await process_planet_attacks(
        new.status.planetActiveEffects,
        old.status.planetActiveEffects,
        "planetEffects",
        ["index", "galacticEffectId"],
        QueueAll,
        batch,
    )

    if new.news_feed is not None and old.news_feed is not None:
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
        ["health"],
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

    if new.war_info is not None and old.war_info is not None:

        infoout = await get_differing_fields(
            old.war_info, new.war_info, to_ignore=["planetInfos"]
        )
        if infoout:
            item = GameEvent(
                mode="change",
                place="info_raw",
                batch=batch,
                value=(new.war_info, infoout),
            )
            superlist.append(item)
            await QueueAll.put([item])
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
        sector_states(new.status, statics),
        sector_states(old.status, statics),
        "sectors",
        "name",
        QueueAll,
        batch,
        ["planetStatus"],
    )
    logs.info("Done detection, stand by...")
    if new.major_order is None:
        if old.major_order is not None:
            new.major_order = old.major_order
    if new.planet_stats is None:
        if old.planet_stats is not None:
            new.planet_stats = old.planet_stats.model_copy(deep=True)

    return superlist


async def detect_loggable_changes_planet(
    old: BaseApiModel, new: BaseApiModel, QueueAll: asyncio.Queue, statics: StaticAll
) -> Tuple[dict, list]:

    batch = int(new.retrieved_at.timestamp())
    superlist = []

    if old.status.time == new.status.time:

        return None

    logs.info("campaigns detection, stand by...")

    planetindexes = []
    for c in new.status.campaigns:
        if not c.planetIndex in planetindexes:
            planetindexes.append(c.planetIndex)

    output = {
        "timestamp": batch,
        "time": new.status.time,
        "imp": new.status.impactMultiplier,
        "gstate": {},
    }
    events = {}
    for evt in new.status.planetEvents:
        events[evt.planetIndex] = evt
    for planet in new.status.planetStatus:
        if planet.index in planetindexes:
            output["gstate"][planet.index] = planet.model_dump()
            if planet.index in events:
                output["gstate"][planet.index]["health"] = events[planet.index].health
            output["gstate"][planet.index].pop("retrieved_at")

    output["gstate"] = [j for j in output["gstate"].values()]
    await QueueAll.put(
        GameEvent(mode="data", place="planets", batch=batch, value=output)
    )
    # logs.info("planet events detection, stand by...")
    # superlist += await process_planet_events(
    #     new.status.planetEvents,
    #     old.status.planetEvents,
    #     "planetevents",
    #     "id",
    #     QueueAll,
    #     batch,
    #     [],
    # )
    # logs.info("planet status detection, stand by...")
    # superlist += await process_planet_events(
    #     new.status.planetStatus,
    #     old.status.planetStatus,
    #     "planets",
    #     "index",
    #     QueueAll,
    #     batch,
    #     [],
    # )
    logs.info("Done detection, stand by...")
    return superlist
