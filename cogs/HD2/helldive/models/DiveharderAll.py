from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel
import discord

from .WarStatus import WarStatus
from .WarInfo import WarInfo
from .WarSummary import WarSummary
from .Assignment import Assignment
from .NewsFeedItem import NewsFeedItem
from .SteamNews import SteamNewsRaw
from .WarId import WarId


def get_differing_fields(
    model1: BaseApiModel, model2: BaseApiModel, lvd=0, to_ignore=[]
) -> dict:
    """Determine which fields within the BaseApiModel are different from each other."""
    if type(model1) is not type(model2):
        raise ValueError("Both models must be of the same type")

    differing_fields = {}
    to_ignore.append("retrieved_at", 'self')
    if lvd>20:
        return 'ERROR'

    def compare_values(val1, val2):
        if isinstance(val1, BaseApiModel) and isinstance(val2, BaseApiModel):
            return get_differing_fields(val1, val2, lvd + 1)
        elif isinstance(val1, list) and isinstance(val2, list):
            list_diffs = {}
            for i, (v1, v2) in enumerate(zip(val1, val2)):
                # print(str(type(v1))[:25], str(type(v2))[:25])
                if isinstance(v1, BaseApiModel) and isinstance(v2, BaseApiModel):
                    differing = get_differing_fields(v1, v2, lvd + 1)
                    if differing:
                        list_diffs[i] = differing
                elif str(v1) != str(v2):
                    list_diffs[i] = {"old": v1, "new": v2}
            return list_diffs if list_diffs else None
        else:
            return str(val1) != str(val2)

    for field in model1.model_fields:
        if field not in to_ignore:
            value1 = model1[field]
            value2 = model2[field]

            diffs = compare_values(value1, value2)
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


def check_compare_value(key, value, target: List[Dict[str, Any]]):
    for s in target:
        if s[key] == value:
            return s
    return None


def process_planet_events(source, target, out, place, key, exclude=[]):
    for event in source:
        oc = check_compare_value(key, event[key], target)
        if not oc:
            out[place]["new"][event[key]] = event
        else:
            differ = get_differing_fields(oc, event, to_ignore=exclude)
            if differ:
                out[place]["changes"][event[key]] = (event, differ)

    for event in target:
        if not check_compare_value(key, event[key], source):
            out[place]["old"][event[key]] = event


def detect_loggable_changes(old: BaseApiModel, new: BaseApiModel, lvd=0) -> dict:
    out = {
        "campaign": {"new": {}, "changes": {}, "old": {}},
        "planetevents": {"new": {}, "changes": {}, "old": {}},
        "planets": {"new": {}, "changes": {}, "old": {}},
        "planetInfos": {"new": {}, "changes": {}, "old": {}},
        "globalEvents": {"new": {}, "changes": {}, "old": {}},
        "news": {"new": {}, "changes": {}, "old": {}},
        "stats_raw": {
            "changes": {},
        },
        "info_raw": {"changes": {}},
    }
    # Check for new campaigns
    rawout = get_differing_fields(
        old.status,
        new.status,
        to_ignore=[
            "time",
            "planetAttacks",
            "impactMultiplier",
            "campaigns",
            "planetStatus",
            "planetEvents",
            "jointOperations",
            "globalEvents",
        ],
    )
    out["stats_raw"]["changes"] = rawout

    infoout = get_differing_fields(
        old.war_info,
        new.war_info,
        to_ignore=["planetInfos"],
    )
    out["info_raw"]["changes"] = infoout
    process_planet_events(new.news_feed, old.news_feed, out, "news", "id")
    process_planet_events(
        new.status.campaigns, old.status.campaigns, out, "campaign", "id"
    )
    process_planet_events(
        new.status.planetEvents, old.status.planetEvents, out, "planetevents", "id"
    )
    process_planet_events(
        new.status.planetStatus,
        old.status.planetStatus,
        out,
        "planets",
        "index",
        ["health", "players"],
    )
    process_planet_events(
        new.status.globalEvents, old.status.globalEvents, out, "globalEvents", "eventId"
    )
    process_planet_events(
        new.war_info.planetInfos, old.war_info.planetInfos, out, "planetInfos", "index"
    )
    # process_planet_events(new.war_info.planetInfos, old.status.planetInfos, out,'planetInfos','index')

    return out
