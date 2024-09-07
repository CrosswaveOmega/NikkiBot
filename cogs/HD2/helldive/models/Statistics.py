from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

from .ABC.utils import (
    human_format as hf,
    select_emoji as emj,
    changeformatif as cfi,
    extract_timestamp as et,
    seconds_to_time_stamp as sts,
)


class Statistics(BaseApiModel):
    """
    None model
        Contains statistics of missions, kills, success rate etc.

    """

    missionsWon: Optional[int] = Field(alias="missionsWon", default=None)

    missionsLost: Optional[int] = Field(alias="missionsLost", default=None)

    missionTime: Optional[int] = Field(alias="missionTime", default=None)

    terminidKills: Optional[int] = Field(alias="terminidKills", default=None)

    automatonKills: Optional[int] = Field(alias="automatonKills", default=None)

    illuminateKills: Optional[int] = Field(alias="illuminateKills", default=None)

    bulletsFired: Optional[int] = Field(alias="bulletsFired", default=None)

    bulletsHit: Optional[int] = Field(alias="bulletsHit", default=None)

    timePlayed: Optional[int] = Field(alias="timePlayed", default=None)

    deaths: Optional[int] = Field(alias="deaths", default=None)

    revives: Optional[int] = Field(alias="revives", default=None)

    friendlies: Optional[int] = Field(alias="friendlies", default=None)

    missionSuccessRate: Optional[int] = Field(alias="missionSuccessRate", default=None)

    accuracy: Optional[int] = Field(alias="accuracy", default=None)

    playerCount: Optional[int] = Field(alias="playerCount", default=None)

    def __sub__(self, other: "Statistics") -> "Statistics":
        return Statistics(
            missionsWon=(self.missionsWon or 0) - (other.missionsWon or 0),
            missionsLost=(self.missionsLost or 0) - (other.missionsLost or 0),
            missionTime=(self.missionTime or 0) - (other.missionTime or 0),
            terminidKills=(self.terminidKills or 0) - (other.terminidKills or 0),
            automatonKills=(self.automatonKills or 0) - (other.automatonKills or 0),
            illuminateKills=(self.illuminateKills or 0) - (other.illuminateKills or 0),
            bulletsFired=(self.bulletsFired or 0) - (other.bulletsFired or 0),
            bulletsHit=(self.bulletsHit or 0) - (other.bulletsHit or 0),
            timePlayed=(self.timePlayed or 0) - (other.timePlayed or 0),
            deaths=(self.deaths or 0) - (other.deaths or 0),
            revives=(self.revives or 0) - (other.revives or 0),
            friendlies=(self.friendlies or 0) - (other.friendlies or 0),
            missionSuccessRate=(self.missionSuccessRate or 0)
            - (other.missionSuccessRate or 0),
            accuracy=(self.accuracy or 0) - (other.accuracy or 0),
            playerCount=(self.playerCount or 0) - (other.playerCount or 0),
        )

    @staticmethod
    def average(stats_list: List["Statistics"]) -> "Statistics":
        count = len(stats_list)
        if count == 0:
            return Statistics()

        avg_stats = Statistics(
            missionsWon=sum(
                stat.missionsWon for stat in stats_list if stat.missionsWon is not None
            )
            // count,
            missionsLost=sum(
                stat.missionsLost
                for stat in stats_list
                if stat.missionsLost is not None
            )
            // count,
            missionTime=sum(
                stat.missionTime for stat in stats_list if stat.missionTime is not None
            )
            // count,
            terminidKills=sum(
                stat.terminidKills
                for stat in stats_list
                if stat.terminidKills is not None
            )
            // count,
            automatonKills=sum(
                stat.automatonKills
                for stat in stats_list
                if stat.automatonKills is not None
            )
            // count,
            illuminateKills=sum(
                stat.illuminateKills
                for stat in stats_list
                if stat.illuminateKills is not None
            )
            // count,
            bulletsFired=sum(
                stat.bulletsFired
                for stat in stats_list
                if stat.bulletsFired is not None
            )
            // count,
            bulletsHit=sum(
                stat.bulletsHit for stat in stats_list if stat.bulletsHit is not None
            )
            // count,
            timePlayed=sum(
                stat.timePlayed for stat in stats_list if stat.timePlayed is not None
            )
            // count,
            deaths=sum(stat.deaths for stat in stats_list if stat.deaths is not None)
            // count,
            revives=sum(stat.revives for stat in stats_list if stat.revives is not None)
            // count,
            friendlies=sum(
                stat.friendlies for stat in stats_list if stat.friendlies is not None
            )
            // count,
            missionSuccessRate=sum(
                stat.missionSuccessRate
                for stat in stats_list
                if stat.missionSuccessRate is not None
            )
            // count,
            accuracy=sum(
                stat.accuracy for stat in stats_list if stat.accuracy is not None
            )
            // count,
            playerCount=sum(
                stat.playerCount for stat in stats_list if stat.playerCount is not None
            )
            // count,
        )

        return avg_stats

    def format_statistics(self) -> str:
        """
        Return statistics formatted in a nice string.
        """
        mission_stats = f"W:{hf(self.missionsWon)},"
        mission_stats += f"L:{hf(self.missionsLost)}"
        missiontime = f"Time:{sts(self.missionTime)} sec"

        # Format kill statistics
        kill_stats = (
            f"T:{hf(self.terminidKills)}, "
            f"A:{hf(self.automatonKills)}, "
            f"DATA EXPUNGED"
        )
        #             f"I: {hf(self.illuminateKills)}"

        # Format deaths and friendlies statistics
        deaths_and_friendlies = (
            f"Deaths/Friendlies: {hf(self.deaths)}/" f"{hf(self.friendlies)}"
        )

        # Format player count
        player_count = f"{emj('hdi')}: {hf(self.playerCount)}"
        thistime = round(
            max(self.missionTime, 1) / max((self.missionsWon + self.missionsLost), 1), 4
        )

        mission_stats += f"\n Time per mission: {sts(thistime)}"
        # Concatenate all formatted statistics
        statsa = (
            f"`[Missions: {mission_stats}]`\n`[{missiontime}]`\n`[Kills: {kill_stats}]`"
        )
        statsb = f"`[{deaths_and_friendlies}]`"
        statsc = f"`Total Time: {sts(self.timePlayed)}`"
        return f"{player_count}\n{statsa}\n{statsb}\n{statsc}"

    def diff_format(self, other: "Statistics") -> str:
        """
        Returns statistics formatted in a nice string with difference from another Statistics class.

        Args:
            other (Statistics): The other Statistics instance to compare with.

        Returns:
            str: Formatted statistics with differences.
        """
        # Calculate differences for each statistic

        # Format each statistic with its difference
        missiontotal = max(1, self.missionsWon + self.missionsLost)
        misiontotalother = max(1, other.missionsWon + other.missionsLost)
        mission_stats = f"W:{hf(self.missionsWon)} ({other.missionsWon}),"
        mission_stats += f"L:{hf(self.missionsLost)} ({other.missionsLost})"
        mission_stats += f"{round(100.0*(other.missionsWon/(max(other.missionsWon+other.missionsLost,1))),1)}"
        mission_stats += f"\nTime:{sts(self.missionTime)}({sts(other.missionTime)})"

        thistime = round(max(self.missionTime, 1) / (missiontotal), 4)
        lasttime = round(max(other.missionTime, 1) / (misiontotalother), 4)
        mission_stats += f"\n Time per mission: {sts(thistime)}({sts(lasttime)})"
        kill_stats = f"T:{hf(self.terminidKills)} ({other.terminidKills}),"
        kill_stats += f"A:{hf(self.automatonKills)} ({other.automatonKills}),"
        kill_stats += "DATA EXPUNGED"
        bullets_stats = f"Bullets Hit/Fired: {hf(self.bulletsHit)}/{hf(self.bulletsFired)} ({other.bulletsHit}/{other.bulletsFired})"
        deaths_and_friendlies = f"Deaths/Friendlies: {hf(self.deaths)}/{hf(self.friendlies)} ({other.deaths}/{other.friendlies})"

        player_count = f"{emj('hdi')}: {hf(self.playerCount)} ({other.playerCount})"

        # Concatenate all formatted statistics
        statsa = f"`[Missions: {mission_stats}]`\n `[Kills: {kill_stats}]`\n`[{bullets_stats}]`"
        statsb = f"`[{deaths_and_friendlies}]`"
        statsc = f"`Total Time: {sts(self.timePlayed)}({sts(other.timePlayed)})`"
        return f"{player_count}\n{statsa}\n{statsb}\n{statsc}"
