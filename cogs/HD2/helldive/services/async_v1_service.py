from typing import List, Optional, Type, TypeVar

import httpx

from ..api_config import APIConfig, HTTPException
from ..models import *
from ..models.ABC.model import BaseApiModel
from .async_direct_service import GetApiDirectAll
from .utils import make_output

T = TypeVar("T", bound=BaseApiModel)
import random
import logging
from logging.handlers import RotatingFileHandler

logslogger = logging.getLogger("logslogger")
# Create a rotating file handler
log_handler = RotatingFileHandler(
    "./logs/logslogger.log", maxBytes=5 * 1024 * 1024, backupCount=5
)
log_handler.setLevel(logging.WARNING)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log_handler.setFormatter(formatter)


log_handler2 = RotatingFileHandler(
    "./logs/logsloggerinfo.log", maxBytes=5 * 1024 * 1024, backupCount=5
)
log_handler2.setLevel(logging.INFO)
# Create a logger and set its level
logslogger.setLevel(logging.INFO)

log_handler2.setFormatter(formatter)

# Set the handler to the logger
logslogger.addHandler(log_handler)

logslogger.addHandler(log_handler2)


async def make_comm_api_request(
    endpoint: str,
    model: Type[T],
    index: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
    path2: bool = False,
) -> Union[T, List[T]]:
    '''Make an API Request for a built object using the Community API Wrapper.'''
    api_config = api_config_override or APIConfig()

    base_path = api_config.api_comm
    path = f"/api/v1/{endpoint}"
    if index is not None:
        path += f"/{index}"
        
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Super-Client": f"{api_config.get_client_name()}",
        # "Authorization": f"Bearer {api_config.get_access_token()}",
    }
    async with httpx.AsyncClient(
        base_url=base_path, verify=api_config.verify, timeout=20.0
    ) as client:
        response = await client.get(path, headers=headers)

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f"Failed with status code: {response.status_code}"
        )
    data = response.json()
    return make_output(data, model, index)


async def make_raw_api_request(
    endpoint: str,
    model: Type[T],
    index: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
    path2=False,
) -> Union[T, List[T]]:
    '''
    Get a raw api object from the Community api or 
    diveharder.
    '''
    api_config = api_config_override or APIConfig()

    base_path = api_config.api_comm
    path = f"/raw/api/{endpoint}"
    if index is not None:
        path += f"/{index}"

    if path2:
        base_path = api_config.api_diveharder
        path = f"/raw/{endpoint}"
        if index is not None:
            path += f"/{index}"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Super-Client": f"{api_config.get_client_name()}",
        # "Authorization": f"Bearer {api_config.get_access_token()}",
    }
    async with httpx.AsyncClient(
        base_url=base_path, verify=api_config.verify, timeout=8.0
    ) as client:
        response = await client.get(path, headers=headers)

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f"Failed with status code: {response.status_code}"
        )
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    data = response.json()
    return make_output(data, model, index)

async def GetApiV1War(api_config_override: Optional[APIConfig] = None) -> War:
    return await make_comm_api_request("war", War, api_config_override=api_config_override)


async def GetApiRawStatus(api_config_override: Optional[APIConfig] = None) -> WarStatus:
    return await make_raw_api_request(
        "WarSeason/801/Status", WarStatus, api_config_override=api_config_override
    )


async def GetApiRawAll(
    api_config_override: Optional[APIConfig] = None, direct=False
) -> DiveharderAll:
    if direct:
        return await GetApiDirectAll(api_config_override=api_config_override)
    try:
        return await make_raw_api_request(
            "all", DiveharderAll, api_config_override=api_config_override, path2=True
        )
    except Exception as e:
        logslogger.error(str(e), exc_info=e)
        return await GetApiDirectAll(api_config_override=api_config_override)


async def GetApiV1AssignmentsAll(
    api_config_override: Optional[APIConfig] = None,
) -> List[Assignment2]:
    return await make_comm_api_request(
        "assignments", Assignment2, api_config_override=api_config_override
    )


async def GetApiV1Assignments(
    index: int, api_config_override: Optional[APIConfig] = None
) -> Assignment2:
    return await make_comm_api_request(
        "assignments", Assignment2, index, api_config_override=api_config_override
    )


async def GetApiV1CampaignsAll(
    api_config_override: Optional[APIConfig] = None,
) -> List[Campaign2]:
    return await make_comm_api_request(
        "campaigns", Campaign2, api_config_override=api_config_override
    )


async def GetApiV1Campaigns(
    index: int, api_config_override: Optional[APIConfig] = None
) -> Campaign2:
    return await make_comm_api_request(
        "campaigns", Campaign2, index, api_config_override=api_config_override
    )


async def GetApiV1DispatchesAll(
    api_config_override: Optional[APIConfig] = None,
) -> List[Dispatch]:
    return await make_comm_api_request(
        "dispatches", Dispatch, api_config_override=api_config_override
    )


async def GetApiV1Dispatches(
    index: int, api_config_override: Optional[APIConfig] = None
) -> Dispatch:
    return await make_comm_api_request(
        "dispatches", Dispatch, index, api_config_override=api_config_override
    )


async def GetApiV1PlanetsAll(
    api_config_override: Optional[APIConfig] = None,
) -> List[Planet]:
    return await make_comm_api_request(
        "planets", Planet, api_config_override=api_config_override
    )


async def GetApiV1Planets(
    index: int, api_config_override: Optional[APIConfig] = None
) -> Planet:
    return await make_comm_api_request(
        "planets", Planet, index, api_config_override=api_config_override
    )


async def GetApiV1PlanetEvents(
    api_config_override: Optional[APIConfig] = None,
) -> List[Planet]:
    return await make_comm_api_request(
        "planet-events", Planet, api_config_override=api_config_override
    )


async def GetApiV1Steam(
    api_config_override: Optional[APIConfig] = None,
) -> List[SteamNews]:
    return await make_comm_api_request(
        "steam", SteamNews, api_config_override=api_config_override
    )


async def GetApiV1Steam2(
    gid: str, api_config_override: Optional[APIConfig] = None
) -> List[SteamNews]:
    return await make_comm_api_request(
        "steam", SteamNews, gid, api_config_override=api_config_override
    )
