import json
from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .Campaign import Campaign
from .JointOperation import JointOperation
from .PlanetAttack import PlanetAttack
from .PlanetEvent import PlanetEvent
from .PlanetStatus import PlanetStatus
from .GlobalEvent import GlobalEvent
from .Position import Position
from .Effects import PlanetActiveEffects


class SectorStates(BaseApiModel):
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


class WarStatus(BaseApiModel):
    """
    None model
        Represents a snapshot of the current status of the galactic war.

    """

    warId: Optional[int] = Field(alias="warId", default=None)

    time: Optional[int] = Field(alias="time", default=None)

    impactMultiplier: Optional[float] = Field(alias="impactMultiplier", default=None)

    storyBeatId32: Optional[int] = Field(alias="storyBeatId32", default=None)

    planetStatus: Optional[List[Optional[PlanetStatus]]] = Field(
        alias="planetStatus", default=[]
    )

    planetAttacks: Optional[List[Optional[PlanetAttack]]] = Field(
        alias="planetAttacks", default=[]
    )

    campaigns: Optional[List[Optional[Campaign]]] = Field(alias="campaigns", default=[])

    jointOperations: Optional[List[Optional[JointOperation]]] = Field(
        alias="jointOperations", default=[]
    )

    planetEvents: Optional[List[Optional[PlanetEvent]]] = Field(
        alias="planetEvents", default=[]
    )

    communityTargets: Optional[List[Any]] = Field(alias="communityTargets", default=[])
    activeElectionPolicyEffects: Optional[List[Any]] = Field(
        alias="activeElectionPolicyEffects", default=[]
    )
    planetActiveEffects: Optional[List[PlanetActiveEffects]] = Field(
        alias="planetActiveEffects", default=[]
    )

    globalEvents: Optional[List[GlobalEvent]] = Field(alias="globalEvents", default=[])

    superEarthWarResults: Optional[List[Any]] = Field(
        alias="superEarthWarResults", default=[]
    )

    layoutVersion: Optional[int] = Field(alias="layoutVersion", default=None)

    def sector_states(self):
        data_path: str = "./hd2json/planets/planets.json"

        with open(data_path, "r") as file:
            planets_data_json = json.load(file)
        sect = {}
        if self.planetStatus:
            for s in self.planetStatus:
                sector = planets_data_json[str(s.index)]["sector"]
                if not sector in sect:
                    sect[sector] = SectorStates(
                        retrieved_at=self.retrieved_at, name=sector, sector=sector
                    )
                sect[sector].planetStatus.append(s)
                sect[sector].check_common_owner()
        return list(sect.values())
