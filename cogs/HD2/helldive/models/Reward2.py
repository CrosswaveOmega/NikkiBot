from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


from utility import (
    human_format as hf,
    select_emoji as emj,
    changeformatif as cfi,
    extract_timestamp as et,
)
from discord.utils import format_dt as fdt


class Reward2(BaseApiModel):
    """
    None model
        The reward for completing an Assignment.

    """

    type: Optional[int] = Field(alias="type", default=None)

    amount: Optional[int] = Field(alias="amount", default=None)

    def format(self):
        """Return the string representation of any reward."""
        if self.type == 1:
            return f"{emj('medal')} × {self.amount}"
        return f"Unknown type:{self.type} × {self.amount}"
