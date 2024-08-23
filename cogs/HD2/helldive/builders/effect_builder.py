from typing import List, Optional, Type, TypeVar, Dict

import httpx

import datetime as dt
from ..api_config import APIConfig, HTTPException
from ..models import *
from ..models.ABC.model import BaseApiModel

from hd2json.jsonutils import load_and_merge_json_files
from ..constants import task_types, value_types, faction_names, samples


def build_planet_effect(self:EffectStatic, idv):
    if self.planetEffects is not None:
        peffect: Dict[int, KnownPlanetEffect] = cast(dict,self.planetEffects)
        if idv in peffect:
            return peffect[idv]
        return KnownPlanetEffect(galacticEffectId=idv, name=f"Effect {idv}", description="Mysterious signature...")
