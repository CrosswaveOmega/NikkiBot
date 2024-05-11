from typing import *

from pydantic import Field
from .ABC.model import BaseApiModel

def human_format(num):
    num = float("{:.3g}".format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    suffixes = ["", "K", "M", "B", "T", "Q", "Qi"]
    return "{}{}".format(
        "{:f}".format(num).rstrip("0").rstrip("."), suffixes[magnitude]
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

    def __sub__(self, other: 'Statistics') -> 'Statistics':
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
            missionSuccessRate=(self.missionSuccessRate or 0) - (other.missionSuccessRate or 0),
            accuracy=(self.accuracy or 0) - (other.accuracy or 0),
            playerCount=(self.playerCount or 0) - (other.playerCount or 0)
        )
        



    def format_statistics(self)->str:
        '''
            Return statistics formatted in a nice string.
        '''
        mission_stats = f"W:{human_format(self.missionsWon)},"
        mission_stats += f"L:{human_format(self.missionsLost)}"
        # mission_stats += f"Time: {human_format(self.missionTime)} seconds"

        # Format kill statistics
        kill_stats = (
            f"T:{human_format(self.terminidKills)}, "
            f"A:{human_format(self.automatonKills)}, "
            f"DATA EXPUNGED"
        )
        #             f"I: {human_format(self.illuminateKills)}"

        # Format bullets statistics
        bullets_fired = self.bulletsFired
        bullets_hit = self.bulletsHit
        bullets_stats = (
            f"Bullets Hit/Fired: {human_format(bullets_hit)}/{human_format(bullets_fired)}"
        )

        # Format deaths and friendlies statistics
        deaths_and_friendlies = (
            f"Deaths/Friendlies: {human_format(self.deaths)}/"
            f"{human_format(self.friendlies)}"
        )

        # Format mission success rate
        mission_success_rate = f"MCR: {self.missionSuccessRate}%"

        # Format accuracy
        accuracy = f"ACC: {self.accuracy}%"

        # Format player count
        player_count = f"Player Count: {human_format(self.playerCount)}"

        # Concatenate all formatted statistics
        statsa = f"`[Missions: {mission_stats}] [Kills: {kill_stats}] [{bullets_stats}]`"
        statsb = f"`[{deaths_and_friendlies}] [{mission_success_rate}] [{accuracy}]`"

        return f"{player_count}\n{statsa}\n{statsb}"
    
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
        mission_stats = f"W:{human_format(self.missionsWon)} ({other.missionsWon}),"
        mission_stats+=f"L:{human_format(self.missionsLost)} ({other.missionsLost})"
        kill_stats = f"T:{human_format(self.terminidKills)} ({other.missionsLost}),"
        kill_stats+=f"A:{human_format(self.automatonKills)} ({other.automatonKills}),"
        kill_stats+="DATA EXPUNGED"
        bullets_stats = f"Bullets Hit/Fired: {human_format(self.bulletsHit)}/{human_format(self.bulletsFired)} ({other.bulletsHit}/{other.bulletsFired})"
        deaths_and_friendlies = f"Deaths/Friendlies: {human_format(self.deaths)}/{human_format(self.friendlies)} ({other.deaths}/{other.friendlies})"
        mission_success_rate = f"MCR: {self.missionSuccessRate}% ({other.missionSuccessRate}%)"
        accuracy = f"ACC: {self.accuracy}% ({other.accuracy}%)"
        player_count = f"Player Count: {human_format(self.playerCount)} ({other.playerCount})"

        # Concatenate all formatted statistics
        statsa = f"`[Missions: {mission_stats}] [Kills: {kill_stats}] [{bullets_stats}]`"
        statsb = f"`[{deaths_and_friendlies}] [{mission_success_rate}] [{accuracy}]`"

        return f"{player_count}\n{statsa}\n{statsb}"
