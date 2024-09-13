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


def build_assignment_2(assignment: Assignment, diveharder: DiveharderAll):
    setting = assignment.setting
    reward = setting.reward
    ret = Assignment2(
        retrieved_at=assignment.retrieved_at,
        id=assignment.id32,
        progress=assignment.progress,
        expiration=(
            assignment.retrieved_at + dt.timedelta(seconds=assignment.expiresIn)
        ).isoformat(),
        briefing=setting.overrideBrief,
        title=setting.overrideTitle,
        description=setting.taskDescription,
        reward=Reward2(
            retrieved_at=reward.retrieved_at,
            type=reward.type,
            amount=reward.amount,
            id32=reward.id32,
        ),
        rewards=[Reward(**r.model_dump()) for r in setting.rewards],
        tasks=[Task2(**t.model_dump()) for t in setting.tasks],
        type=setting.type,
        flags=setting.flags,
    )

    return ret


def build_all_assignments(assignments: List[Assignment], diveharder: DiveharderAll):
    assignment_2 = []
    if assignments is None:
        return []
    for a in assignments:
        assignment_2.append(build_assignment_2(a, diveharder))
    return assignment_2
