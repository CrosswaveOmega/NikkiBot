import json
from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .Base import PlanetStatus


class SectorStates(BaseApiModel):
    """A in game sector with all planets."""

    name: Optional[str] = Field(alias="name", default=None)
    planetStatus: Optional[List[Optional[PlanetStatus]]] = Field(
        alias="planetStatus", default=[]
    )
    sector: Optional[str] = Field(alias="name", default=None)
    owner: Optional[int] = Field(alias="owner", default=0)

    def __init__(self, **data):
        super().__init__(**data)
        self.check_common_owner()

    def check_common_owner(self):
        owners = {
            ps.owner
            for ps in self.planetStatus
            if ps is not None and ps.owner is not None
        }
        if len(owners) == 1:
            self.owner = owners.pop()
        else:
            self.owner = None
