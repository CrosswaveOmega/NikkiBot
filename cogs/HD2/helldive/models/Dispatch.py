from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

import re


from .ABC.utils import (
    human_format as hf,
    select_emoji as emj,
    changeformatif as cfi,
    extract_timestamp as et,
    hdml_parse,
    format_datetime as fdt,
)


class Dispatch(BaseApiModel):
    """
    None model
        A message from high command to the players, usually updates on the status of the war effort.

    """

    id: Optional[int] = Field(alias="id", default=None)

    published: Optional[str] = Field(alias="published", default=None)

    type: Optional[int] = Field(alias="type", default=None)

    message: Optional[Union[str, Dict[str, Any]]] = Field(alias="message", default=None)

    def get_text_and_time(self) -> tuple[str, Optional[str]]:
        # Replace the matched patterns with markdown bold syntax
        converted_text = hdml_parse(self.message)
        extract_time = et(self.published)
        return converted_text, extract_time
