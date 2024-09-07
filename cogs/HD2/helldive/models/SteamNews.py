from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class SteamNews(BaseApiModel):
    """
    None model
        Represents a new article from Steam&#39;s news feed.

    """

    id: Optional[str] = Field(alias="id", default=None)

    title: Optional[str] = Field(alias="title", default=None)

    url: Optional[str] = Field(alias="url", default=None)

    author: Optional[str] = Field(alias="author", default=None)

    content: Optional[str] = Field(alias="content", default=None)

    publishedAt: Optional[str] = Field(alias="publishedAt", default=None)
