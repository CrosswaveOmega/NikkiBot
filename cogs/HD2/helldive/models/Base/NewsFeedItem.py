from typing import *

from pydantic import Field
from ..ABC.model import BaseApiModel
from ..ABC.utils import hdml_parse
import re


class NewsFeedItem(BaseApiModel):
    """
    None model
        Represents an item in the newsfeed of Super Earth.

    """

    id: Optional[int] = Field(alias="id", default=None)

    published: Optional[int] = Field(alias="published", default=None)

    type: Optional[int] = Field(alias="type", default=None)

    message: Optional[str] = Field(alias="message", default=None)

    def to_str(self) -> Tuple[str, str]:
        # message=self.# Replace the matched patterns with markdown bold syntax
        converted_text = hdml_parse(self.message if self.message else "INVALID")
        extract_time = self.published
        return (
            f"Dispatch {self.id}, type {self.type}",
            f"{converted_text}\n published at: {(extract_time)}",
        )
