from typing import List, Optional, Type, TypeVar

import httpx

from ..api_config import APIConfig, HTTPException
from ..models import *
from ..models.ABC.model import BaseApiModel
from .utils import make_output
T = TypeVar("T", bound=BaseApiModel)

import logging

# Create a logger and set its level
logslogger = logging.getLogger("logslogger")
logslogger.setLevel(logging.INFO)

async def make_direct_api_request(
    endpoint: str,
    model: Type[T],
    index: Optional[int] = None,
    api_config_override: Optional[APIConfig] = None,
    path2=False,
    params: Optional[dict] = None,  # Added parameters for GET requests
) -> Union[T, List[T]]:
    '''Get a raw api object directly from arrowhead's api.'''
    api_config = api_config_override or APIConfig()

    base_path = api_config.api_direct
    path = f"/api/{endpoint}"
    if index is not None:
        path += f"/{index}"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Super-Client": f"{api_config.get_client_name()}",
        "Accept-Language": api_config.language,
        # "Authorization": f"Bearer {api_config.get_access_token()}",
    }
    try:
        async with httpx.AsyncClient(
            base_url=base_path, verify=api_config.verify, timeout=8.0
        ) as client:
            if params:
                response = await client.get(
                    path, headers=headers, params=params
                )  # Added params to the request
            else:
                response = await client.get(
                    path, headers=headers
                )  # Added params to the request
    except httpx.ConnectError as e:
        print(e)
        logslogger.error(str(e), exc_info=e)
        raise e
    except Exception as e:
        print(e)
        logslogger.error(str(e), exc_info=e)
        return None

    if response.status_code != 200:
        raise HTTPException(
            response.status_code, f"Failed with status code: {response.status_code}"
        )
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    data = response.json()
    if isinstance(data, dict):
        logslogger.info(
            "%s",
            ",".join(f"{k}:{len(json.dumps(v,default=str))}" for k, v in data.items()),
        )
    else:
        logslogger.info("%s", "LIST")

    return make_output(data, model, index)


async def GetApiDirectWarStatus(api_config_override: Optional[APIConfig]) -> WarStatus:
    return await make_direct_api_request(
        "WarSeason/801/Status",
        WarStatus,
        api_config_override=api_config_override,
        path2=True,
    )

async def GetApiDirectWarInfo(api_config_override: Optional[APIConfig]) -> WarInfo:
    return await make_direct_api_request(
        "WarSeason/801/WarInfo",
        WarInfo,
        api_config_override=api_config_override,
        path2=True,
    )

async def GetApiDirectSummary(api_config_override: Optional[APIConfig]) -> WarSummary:
    return await make_direct_api_request(
        "Stats/War/801/Summary",
        WarSummary,
        api_config_override=api_config_override,
        path2=True,
    )

async def GetApiDirectAssignment(api_config_override: Optional[APIConfig]) -> Assignment:
    return await make_direct_api_request(
        "v2/Assignment/War/801",
        Assignment,
        api_config_override=api_config_override,
        path2=True,
    )

async def GetApiDirectNewsFeed(api_config_override: Optional[APIConfig]) -> List[NewsFeedItem]:
    return await make_direct_api_request(
        "NewsFeed/801",
        NewsFeedItem,
        api_config_override=api_config_override,
        path2=True,
        params={"maxEntries": 1024},
    )


async def GetApiDirectAll(
    api_config_override: Optional[APIConfig] = None, direct=False
) -> DiveharderAll:
    warstatus = await GetApiDirectWarStatus(api_config_override)
    warinfo = await GetApiDirectWarInfo(api_config_override)
    summary = await GetApiDirectSummary(api_config_override)
    assign = await GetApiDirectAssignment(api_config_override)
    news = await GetApiDirectNewsFeed(api_config_override)

    newdive = DiveharderAll(
        status=warstatus,
        war_info=warinfo,
        planet_stats=summary,
        major_order=assign,
        news_feed=news,
    )
    return newdive
