from typing import *


from pydantic import Field
from .ABC.model import BaseApiModel


from .Base.WarStatus import WarStatus
from .Base.WarInfo import WarInfo
from .Base.WarSummary import WarSummary
from .Base.Assignment import Assignment
from .Base.NewsFeedItem import NewsFeedItem
from .Base.SteamNewsRaw import SteamNewsRaw
from .Base.WarId import WarId


class DiveharderAll(BaseApiModel):
    """
    Everything returned from the api in one convienent package.

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
