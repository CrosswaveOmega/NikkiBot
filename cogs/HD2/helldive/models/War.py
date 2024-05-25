from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .Statistics import Statistics


class War(BaseApiModel):
    """
    None model
        Global information of the ongoing war.

    """

    started: Optional[str] = Field(alias="started", default=None)

    ended: Optional[str] = Field(alias="ended", default=None)

    now: Optional[str] = Field(alias="now", default=None)

    clientVersion: Optional[str] = Field(alias="clientVersion", default=None)

    factions: Optional[List[str]] = Field(alias="factions", default=None)

    impactMultiplier: Optional[float] = Field(alias="impactMultiplier", default=None)

    statistics: Optional[Statistics] = Field(alias="statistics", default=None)

    def __sub__(self, other):
        war = War(
            started=self.started,
            ended=self.ended,
            now=self.now,
            clientVersion=self.clientVersion,
            factions=self.factions,
            impactMultiplier=self.impactMultiplier - other.impactMultiplier,
            statistics=self.statistics - other.statistics,
        )
        return war
