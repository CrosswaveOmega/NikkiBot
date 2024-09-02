from typing import List, Optional, Type, TypeVar

import httpx

from ..api_config import APIConfig, HTTPException
from ..models import *
from ..models.ABC.model import BaseApiModel

T = TypeVar("T", bound=BaseApiModel)

import logging
from logging.handlers import RotatingFileHandler

# Create a rotating file handler
log_handler = RotatingFileHandler('./logs/logslogger.log', maxBytes=5*1024*1024, backupCount=5)
log_handler.setLevel(logging.WARNING)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)


log_handler2 = RotatingFileHandler('./logs/logsloggerinfo.log', maxBytes=5*1024*1024, backupCount=5)
log_handler2.setLevel(logging.INFO)
# Create a logger and set its level
logslogger = logging.getLogger("logslogger")
logslogger.setLevel(logging.INFO)

log_handler2.setFormatter(formatter)

# Set the handler to the logger
logslogger.addHandler(log_handler)

logslogger.addHandler(log_handler2)

async def make_api_request(
    endpoint: str,
    model: Type[T],
    index: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
    path2: bool = False,
) -> Union[T, List[T]]:
    api_config = api_config_override or APIConfig()

    base_path = api_config.base_path
    path = f"/api/v1/{endpoint}"
    if index is not None:
        path += f"/{index}"

    if path2:
        base_path = api_config.base_path_2
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
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    data = response.json()
    if index is not None:
        if isinstance(data, dict):
            if data:
                mod = model(**data)
                mod.retrieved_at = now
                return mod
            return model()
        elif isinstance(data, list):
            if data:
                mod = model(**data[0])
                mod.retrieved_at = now
                return mod
            return model()
    else:
        if isinstance(data, list):
            models = []
            for item in data:
                mod = model(**item)
                mod.retrieved_at = now
                models.append(mod)
            return models
        elif isinstance(data, dict):
            if data:
                mod = model(**data)
                mod.retrieved_at = now
                return mod
            return {}


async def make_raw_api_request(
    endpoint: str,
    model: Type[T],
    index: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
    path2=False,
) -> Union[T, List[T]]:
    api_config = api_config_override or APIConfig()

    base_path = api_config.base_path
    path = f"/raw/api/{endpoint}"
    if index is not None:
        path += f"/{index}"

    if path2:
        base_path = api_config.base_path_2
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
    if index is not None:
        if isinstance(data, dict):
            if data:
                mod = model(**data)
                mod.retrieved_at = now
                return mod
            return model()
        elif isinstance(data, list):
            if data:
                mod = model(**data[0])
                mod.retrieved_at = now
                return mod
            return model()
    else:
        if isinstance(data, list):
            models = []
            for item in data:
                mod = model(**item)
                mod.retrieved_at = now
                models.append(mod)
            return models
        elif isinstance(data, dict):
            if data:
                mod = model(**data)
                mod.retrieved_at = now
                return mod
            return {}

async def make_direct_api_request(
    endpoint: str,
    model: Type[T],
    index: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
    path2=False,
    params: Optional[dict] = None,  # Added parameters for GET requests
) -> Union[T, List[T]]:
    api_config = api_config_override or APIConfig()

    base_path = api_config.base_path_3
    path = f"/api/{endpoint}"
    if index is not None:
        path += f"/{index}"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Super-Client": f"{api_config.get_client_name()}",
        "Accept-Language":	'en-US'
        # "Authorization": f"Bearer {api_config.get_access_token()}",
    }
    try:
        async with httpx.AsyncClient(
            base_url=base_path, verify=api_config.verify, timeout=8.0
        ) as client:
            if params:
               response = await client.get(path, headers=headers,params=params)  # Added params to the request
            else:
               response = await client.get(path, headers=headers)  # Added params to the request
    except Exception as e:
        print(e)
        logslogger.error(str(e),exc_info=e)
        return None

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f"Failed with status code: {response.status_code}"
        )
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    data = response.json()
    logslogger.info("%s",json.dumps(data))
    if index is not None:
        if isinstance(data, dict):
            if data:
                mod = model(**data)
                mod.retrieved_at = now
                return mod
            return model()
        elif isinstance(data, list):
            if data:
                mod = model(**data[0])
                mod.retrieved_at = now
                return mod
            return model()
    else:
        if isinstance(data, list):
            models = []
            for item in data:
                mod = model(**item)
                mod.retrieved_at = now
                models.append(mod)
            return models
        elif isinstance(data, dict):
            if data:
                mod = model(**data)
                mod.retrieved_at = now
                return mod
            return {}
        


async def GetApiV1War(api_config_override: Optional[APIConfig] = None) -> War:
    return await make_api_request("war", War, api_config_override=api_config_override)


async def GetApiRawStatus(api_config_override: Optional[APIConfig] = None) -> WarStatus:
    return await make_raw_api_request(
        "WarSeason/801/Status", WarStatus, api_config_override=api_config_override
    )


async def GetApiDirectAll(
    api_config_override: Optional[APIConfig] = None, direct=False
) -> DiveharderAll:
    warstatus= await make_direct_api_request(
        "WarSeason/801/Status", WarStatus, api_config_override=api_config_override, path2=True
    )
    warinfo= await make_direct_api_request(
        "WarSeason/801/WarInfo", WarInfo, api_config_override=api_config_override, path2=True
    )
    summary= await make_direct_api_request(
        "Stats/War/801/Summary", WarSummary, api_config_override=api_config_override, path2=True
    )
    
    assign= await make_direct_api_request(
        "v2/Assignment/War/801", Assignment, api_config_override=api_config_override, path2=True
    )
    news= await make_direct_api_request(
        "NewsFeed/801", NewsFeedItem, api_config_override=api_config_override, path2=True, params={
            'maxEntries':1024
        }
    )
    newdive=DiveharderAll(status=warstatus,war_info=warinfo,planet_stats=summary,major_order=assign,news_feed=news)
    return newdive



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
        logslogger.error(str(e),exc_info=e)
        return await GetApiDirectAll(api_config_override=api_config_override)

        




async def GetApiV1AssignmentsAll(
    api_config_override: Optional[APIConfig] = None,
) -> List[Assignment2]:
    return await make_api_request(
        "assignments", Assignment2, api_config_override=api_config_override
    )


async def GetApiV1Assignments(
    index: int, api_config_override: Optional[APIConfig] = None
) -> Assignment2:
    return await make_api_request(
        "assignments", Assignment2, index, api_config_override=api_config_override
    )


async def GetApiV1CampaignsAll(
    api_config_override: Optional[APIConfig] = None,
) -> List[Campaign2]:
    return await make_api_request(
        "campaigns", Campaign2, api_config_override=api_config_override
    )


async def GetApiV1Campaigns(
    index: int, api_config_override: Optional[APIConfig] = None
) -> Campaign2:
    return await make_api_request(
        "campaigns", Campaign2, index, api_config_override=api_config_override
    )


async def GetApiV1DispatchesAll(
    api_config_override: Optional[APIConfig] = None,
) -> List[Dispatch]:
    return await make_api_request(
        "dispatches", Dispatch, api_config_override=api_config_override
    )


async def GetApiV1Dispatches(
    index: int, api_config_override: Optional[APIConfig] = None
) -> Dispatch:
    return await make_api_request(
        "dispatches", Dispatch, index, api_config_override=api_config_override
    )


async def GetApiV1PlanetsAll(
    api_config_override: Optional[APIConfig] = None,
) -> List[Planet]:
    return await make_api_request(
        "planets", Planet, api_config_override=api_config_override
    )


async def GetApiV1Planets(
    index: int, api_config_override: Optional[APIConfig] = None
) -> Planet:
    return await make_api_request(
        "planets", Planet, index, api_config_override=api_config_override
    )


async def GetApiV1PlanetEvents(
    api_config_override: Optional[APIConfig] = None,
) -> List[Planet]:
    return await make_api_request(
        "planet-events", Planet, api_config_override=api_config_override
    )


async def GetApiV1Steam(
    api_config_override: Optional[APIConfig] = None,
) -> List[SteamNews]:
    return await make_api_request(
        "steam", SteamNews, api_config_override=api_config_override
    )


async def GetApiV1Steam2(
    gid: str, api_config_override: Optional[APIConfig] = None
) -> List[SteamNews]:
    return await make_api_request(
        "steam", SteamNews, gid, api_config_override=api_config_override
    )
