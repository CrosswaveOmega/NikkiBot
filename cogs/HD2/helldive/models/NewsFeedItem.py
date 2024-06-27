from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


class NewsFeedItem(BaseApiModel):
    """
    None model
        Represents an item in the newsfeed of Super Earth.

    """

    id: Optional[int] = Field(alias="id", default=None)

    published: Optional[int] = Field(alias="published", default=None)

    type: Optional[int] = Field(alias="type", default=None)

    message: Optional[str] = Field(alias="message", default=None)
