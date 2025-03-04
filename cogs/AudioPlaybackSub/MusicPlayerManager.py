from typing import Union
import discord
from .MusicPlayer import MusicPlayer


class MusicPlayers:
    """class that stores a dictionary of all active music player, managed per guild."""

    def __init__(self):
        self.players = {}

    def add_player(self, bot, guild: discord.Guild):
        key = str(guild.id)
        if key not in self.players:
            newplayer = MusicPlayer(bot, guild)
            self.players[key] = newplayer

    def getplayer(self, guild: discord.Guild) -> MusicPlayer:
        """get a music player object."""
        key = str(guild.id)
        if key in self.players:
            return self.players[key]
        return None

    def gp(self, interaction_or_guild):
        if isinstance(interaction_or_guild, type(discord.Interaction)):
            return self.getplayer(interaction_or_guild.guild)
        if isinstance(interaction_or_guild, type(discord.Guild)):
            return self.getplayer(interaction_or_guild)

    def allplayers(self):
        """An iterator that walks through all the music players.
        Yields
        ------
        Union[:class:`.MusicPlayer`, :class:`None`]
            A command or group from the cog.
        """
        for gid, play in self.players.items():
            yield play

    def remove_player(self, guild: discord.Guild) -> MusicPlayer:
        """remove a music player for the passed in discord Guild"""
        key = str(guild.id)
        if key in self.players:
            ret = self.players.pop(key)
            return ret
        return None


class MusicManager:
    """this class just provides a single interface to MusicPlayers."""

    _music_players = None

    @classmethod
    def initialize(cls):
        if cls._music_players is None:
            cls._music_players = MusicPlayers()

    @classmethod
    def add_player(cls, bot, guild: discord.Guild):
        cls.initialize()
        cls._music_players.add_player(bot, guild)

    @classmethod
    def get_player(cls, guild: discord.Guild) -> MusicPlayer:
        cls.initialize()
        return cls._music_players.getplayer(guild)

    @classmethod
    def get(cls, guild: discord.Guild) -> MusicPlayer:
        return cls.get_player(guild)

    @classmethod
    def get_player_by_interaction_or_guild(
        cls, inter: Union[discord.Interaction, discord.Guild]
    ) -> MusicPlayer:
        cls.initialize()
        return cls._music_players.gp(inter)

    @classmethod
    def all_players(cls):
        cls.initialize()
        return cls._music_players.allplayers()

    @classmethod
    def remove_player(cls, guild: discord.Guild) -> MusicPlayer:
        cls.initialize()
        return cls._music_players.remove_player(guild)
