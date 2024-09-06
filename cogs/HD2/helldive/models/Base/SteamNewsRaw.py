from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel


class SteamNewsRaw(BaseApiModel):
    """
    None model
        Represents a new article from Steam&#39;s news feed.

    """

    title: Optional[str] = Field(alias="title", default=None)

    url: Optional[str] = Field(alias="url", default=None)

    contents: Optional[str] = Field(alias="contents", default=None)

    date: Optional[str] = Field(alias="date", default=None)
