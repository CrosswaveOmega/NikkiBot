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


from utility import (
    human_format as hf,
    select_emoji as emj,
    changeformatif as cfi,
    extract_timestamp as et,
)
from discord.utils import format_dt as fdt

# Define the regex pattern to match <i=1>...</i> tags
pattern = r"<i=1>(.*?)<\/i>"
pattern3 = r"<i=3>(.*?)<\/i>"


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
