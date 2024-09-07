from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel


from .ABC.utils import (
    human_format as hf,
    select_emoji as emj,
    changeformatif as cfi,
    extract_timestamp as et,
)

from ..constants import rewards


class Reward2(BaseApiModel):
    """
    None model
        The reward for completing an Assignment.

    """

    type: Optional[int] = Field(alias="type", default=None)

    id32: Optional[int] = Field(alias="id32", default=None)

    amount: Optional[int] = Field(alias="amount", default=None)

    def format(self):
        """Return the string representation of any reward."""
        type = self.type
        if self.id32 in rewards:
            type = rewards[self.id32]
        if type == 1:
            return f"{emj('medal')} × {self.amount}"
        if type == 2:
            return f"{emj('req')} × {self.amount}"
        if type == 3:
            return f"{emj('credits')} × {self.amount}"

        return f"Unknown type:{self.type} × {self.amount}"
