from typing import *
from ..models import *


def sector_states(war_status: WarStatus, statics: StaticAll) -> List[SectorStates]:
    """
    Organizes planetary war status by sector.

    Args:
        war_status (WarStatus): An object containing the current war status, including a list of planet statuses.
        statics (StaticAll): An object containing static data, including galaxy and planet information.

    Returns:
        list[SectorStates]: A list of SectorStates objects, each representing the war status of a sector.
    """
    planets = statics.galaxystatic.planets
    sect = {}
    if war_status.planetStatus:
        for s in war_status.planetStatus:
            planet = planets.get(int(s.index), None)
            if not planet:
                continue
            sector = planet.sector
            if not sector in sect:
                sect[sector] = SectorStates(
                    retrieved_at=war_status.retrieved_at, name=sector, sector=sector
                )
            sect[sector].planetStatus.append(s)
            sect[sector].check_common_owner()
    return list(sect.values())
