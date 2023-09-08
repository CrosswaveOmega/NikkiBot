import asyncio
from typing import(
    Literal,
    Tuple,
    Union,
    
    )
from .AudioContainer import AudioContainer
import random
import discord

from discord.ext import commands, tasks

'''
I'm putting the playback/playlist management functions in these two mixins because MusicPlayer was getting crowded.
'''
class PlayerMixin:
    def setup_actions(self):
        '''Mapping of the mixin's functions to a dictionary.'''
        self.action_dict = {
            "play": self.play,
            "stop": self.stop,
            "pause": self.pause,
            "next": self.next,
            "back": self.back,
            "auto_next": self.next_auto,
            "auto_over": self.next_auto,
            "repeat":self.repeat_toggle,
            "playlistview":self.playlist_view
        }
    async def repeat_toggle(self,ctx: commands.Context, editinter: discord.Interaction = None):
        '''switch repeats to on or off.'''
        if self.repeat==False:
            self.repeat=True
            self.repeatone=False
            await self.send_message(ctx, "repeat", f"Repeat enabled.", editinter)
        elif self.repeat==True:
            self.repeat=False
            self.repeatone=False
            await self.send_message(ctx, "repeat", f"Repeat disabled.", editinter)
    async def play(self, ctx: commands.Context, editinter: discord.Interaction = None):
        """Start playing or resume playing the AudioContainer at self.current.

        Args:
            ctx (commands.Context): The context of the command invocation.
            editinter (discord.Interaction, optional): The interaction object for editing the response message. Defaults to None.
        """
        voice = self.voice
        if self.voice==None:
            await self.send_message(ctx, "voice was never set!", editinter)
        if self.current is None:
            self.player_condition = "play"
            await self.play_song(ctx)
        else:
            if voice.is_paused():
                self.player_condition = "play"
                self.current.resume()
                voice.resume()
                data = self.current
                await self.send_message(ctx, "Resume", f"{data.title} is resuming!", editinter)
            else:
                data = self.current
                await self.send_message(ctx, "Resume", f"{data.title} is already playing!", editinter)

    async def stop(self, ctx, editinter: discord.Interaction = None):
        """Stop the currently playing song and reset the player state.

        Args:
            ctx (commands.Context): The context of the command invocation.
            editinter (discord.Interaction, optional): The interaction object for editing the response message. Defaults to None.
        """
        if self.current is not None:
            self.current.stop()

            if self.repeat:
                self.songs.append(self.current)
            self.player_condition = "stop"
            
            self.current = None
            self.voice.stop()
            await self.send_message(ctx, "Stop", "The player has been stopped.", editinter)

    async def pause(self, ctx: commands.Context, editinter: discord.Interaction = None):
        """Pause the currently playing song.

        Args:
            ctx (commands.Context): The context of the command invocation.
            editinter (discord.Interaction, optional): The interaction object for editing the response message. Defaults to None.
        """
        if self.current is not None:
            if self.voice.is_playing():
                self.voice.pause()
                if not self.override:
                    if self.current:
                        self.current.pause()
                    self.player_condition = "pause"
                    await self.send_message(ctx, "Pause", f"I have paused {self.current.title}!", editinter)
            else:
                await self.send_message(ctx, "Not playing", "There isn't a song playing right now.", editinter)
        else:
            await self.send_message(ctx, "Not playing", "There isn't a song playing right now.", editinter)

    async def next_auto(self,ctx:commands.Context, editinter: discord.Interaction = None):
        await self.next(ctx,editinter,case='auto')

    async def next(self, ctx: commands.Context, editinter: discord.Interaction = None, case="notauto"):
        """Play the next song in the playlist.

        Args:
            ctx (commands.Context): The context of the command invocation.
            editinter (_type_): The interaction object for editing the response message.
            case (str, optional): optional string to determine if next is called via user, or at the end of current's playback

        Returns:
            None
        """
        if self.player_condition=='stop':
            await self.send_message(ctx, "Stopped", "Stopped.",
                                    editinter)
            self.bot.remove_act("MusicPlay")
            self.player_condition = "none"
            return
        if self.repeatone and case == "auto":
            if self.current is not None:
                self.songs.insert(0, self.current)
        elif self.repeat:
            if self.current is not None:
                self.current.stop()
                self.songs.append(self.current)
        elif self.current is not None:
            self.current.stop()
            if len(self.songhist) >= 16:
                self.songhist.pop(0)
            self.songhist.append(self.current)

        if self.songs:
            await self.play_song(ctx)
        else:
            if self.current is not None:
                self.current.stop()
                self.current = None
            await self.send_message(ctx, "Empty Playlist", "My playlist is expended, so I can't go to a new song.",
                                    editinter)
            self.bot.remove_act("MusicPlay")
            self.player_condition = "none"

    async def back(self, ctx: commands.Context, editinter: discord.Interaction = None):
        """Go back to the previous song in the playlist.

        Args:
            ctx (commands.Context): The context of the command invocation.
            editinter (_type_): The interaction object for editing the response message.

        Returns:
            None
        """
        if self.current is not None:
            self.songs.insert(0, self.current)
        if self.repeat:
            back = self.songs.pop()
            self.songs.insert(0, back)
        else:
            if self.songhist:
                torepeat = self.songhist.pop()
                self.songs.insert(0, torepeat)
        if self.songs:
            await self.play_song(ctx)
        else:
            await self.send_message(ctx, "Empty Playlist", "There's nothing to go back to!", editinter)
            self.player_condition = "none"



    async def player_actions(self, action: Literal['','play','stop','pause','next','back','auto_next','auto_over']="", ctxmode: commands.Context = None, editinter: discord.Interaction = None):
        """Dispatch a player action based on the passed in string action.
        'play' : play or resume the current song.
        'stop' : stop the current song and reset the player
        'pause': Pause the current song
        'next' : Play the next song
        'back' : play the previous song
        'auto_next'/'auto_over': called whenever the current song is done playing.
        action=[play,stop,pause,next,auto_next]
        ctxmode: command context if available."""
        ctx, voice = self.channel, self.voice
        if ctxmode:
            ctx = ctxmode
        if self.override != True:
            if action in self.action_dict:
                await self.action_dict[action](ctx, editinter)



class PlaylistMixin:
    '''
    A separate mixin class just for specifying playlist related actions.
    '''

    async def playlist_action_add(self, param:AudioContainer)->AudioContainer:
        """
        Add an AudioContainer to the playlist.

        Args:
            param (AudioContainer): The song to add.

        Returns:
            AudioContainer: The added song.
        """
        song = param
        self.songs.append(song)
        if self.autoshuffle:
            random.shuffle(self.songs)
        return song

    async def playlist_action_add_url(self, param:Tuple[str,str], do_search:bool=True, ignore_error:bool=False)->AudioContainer:
        """
        Create an AudioContainer from a URL and add it to the playlist

        Args:
            param (str): The URL of the song.

        Returns:
            AudioContainer: The added song.
        """
        url, author = param
        song = AudioContainer(url, author.name)
        song.get_song(do_search)

        if song.state == "Error" and not ignore_error:
            if self.channel is not None:
                self.internal_message_log.append(f"I could not add {song.title} : `{str(song.error_value)}`")
                await self.send_message(self.channel, str(song.error_value), desc="Error...")
            await self.bot.send_error(song.error_value, "Adding URL.")
            return None
        elif song.state == "Error" and ignore_error:
            return song.error_value
        else:
           res = await self.playlist_action_add(song)
           return res
    
    async def playlist_action_removespot(self, param:int)->Union[AudioContainer, str]:
        """
        Remove a song from the playlist at a specific spot.

        Args:
            param (int): The spot index of the song to remove.

        Returns:
            Union[AudioContainer, str]: The removed song if successful, or an error message.
        """
        spot = param
        if 0 <= spot < len(self.songs):
            removed_song = self.songs.pop(spot)
            return removed_song
        return "ERR!&outofrange&ERR!"

    async def playlist_action_jumpto(self, param:int)->Union[AudioContainer, str]:
        """
        Move a song to the beginning of the playlist at a specific spot.

        Args:
            param (int): The spot index of the song to move.

        Returns:
            Union[AudioContainer, str]: The moved song if successful, or an error message.
        """
        spot = param
        if 0 <= spot < len(self.songs):
            removed_song = self.songs.pop(spot)
            self.songs.insert(0, removed_song)
            return removed_song
        return "ERR!&outofrange&ERR!"

    async def playlist_action_shuffle(self, param)->str:
        """
        Shuffle the songs in the playlist.

        Returns:
            str: Confirmation message.
        """
        random.shuffle(self.songs)
        return "done"

    async def playlist_action_clear(self,param)->str:
        """
        Clear the playlist.

        Returns:
            str: Confirmation message.
        """
        await self.player_actions("stop")
        if self.songs:
            self.songs, self.current = [], None
            return 'done'
        else:
            return 'emptyalready'

    async def playlist_repeat(self):
        if self.repeat==False:
            self.repeat=True
            self.repeatone=False
        elif self.repeat==True:
            self.repeat=False
            self.repeatone=False
    def setup_playlist_actions(self):
        """
        Set up the dictionary for playlist actions.
        """
        self.playlist_action_dict = {
            "add": self.playlist_action_add,
            "add_url": self.playlist_action_add_url,
            "removespot": self.playlist_action_removespot,
            "jumpto": self.playlist_action_jumpto,
            "shuffle": self.playlist_action_shuffle,
            "clear": self.playlist_action_clear,
            'repeat': self.playlist_repeat
        }

    async def playlist_actions(self, action: Literal['add','add_url','removespot','jumpto','shuffle','clear'], param=None, **kwargs):
        """
        Dispatch a playlist action based on the passed in string action.
        'add'       : Add a AudioContainer to the playlist
        'add_url'   : Create an AudioContainer from a passed in url
        'removespot': Remove 
        'jumpto'    : Play the next song
        'shuffle'   : play the previous song
        'clear':    : called whenever the current song is done playing.
        action=[play,stop,pause,next,auto_next]
        ctxmode: command context if available.
        Perform some action on the playlist.

        Args:
            action (str): The action to perform (add, add_url, removespot, jumpto, shuffle, clear).
            param (Any, optional): The parameter required for certain actions. Defaults to None.

        Returns:
            Any: The result of the action performed.
        """
        if action in self.playlist_action_dict:
            return await self.playlist_action_dict[action](param, **kwargs)

        return "Playlist Command Error"
