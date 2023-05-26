import asyncio
import datetime
import random
import urllib 

import discord
import logging
from discord import app_commands, Embed, Colour
from discord.app_commands import Choice
from discord.ext import commands, tasks
import re
from functools import partial
from queue import Queue
from typing import  Union

from assets import AssetLookup
from utility import  seconds_to_time_string, seconds_to_time_stamp
from utility import PageClassContainer
from .AudioContainer import AudioContainer
from .MusicUtils import connection_check
'''this code is for the music player, and it's interactions.'''

class PlaylistPageContainer(PageClassContainer):
    #Class to extend.
    def __init__(self,inter,musiccomm, player):
        self.this_interaction=inter
        self.guild=inter.guild
        self.musiccom=musiccomm
        self.last_inter=None
        self.player=player
        display=self.musiccom.make_playlist_embeds(inter)

        super(PlaylistPageContainer,self).__init__(display)
    async def playlistcallback(self, interaction, view, result):
        c = 0
        if interaction!=None:
            self.last_inter=interaction
        if (result == 'timeout' or result == 'exit'):
            running = False
            ve=view.clear_items()
            await self.last_inter.response.edit_message(view=ve)
        else:
            if result =="shuffle":
                await self.player.playlist_actions("shuffle")
                self.display=self.musiccom.make_playlist_embeds(self.this_interaction)
            if result == "next":
                self.spot = self.spot + self.perpage
                if (self.spot) >= self.length:
                    self.spot = self.spot %self.length
            if result == "back":
                self.spot = self.spot - self.perpage
                if self.spot < 0:
                    self.spot = self.length+self.spot
            if result == "first":
                self.spot = 0
            if result == "last":
                self.spot = self.largest_spot
                
            emb=self.make_embed()
            await self.last_inter.response.edit_message(embed=emb,view=view)

class MusicPlayer():
    """The class which plays songs."""
    def __init__(self, bot,guild:discord.Guild=None):
        self.bot, self.guild = bot, guild
        self.songs, self.songhist,self.current= [], [],None
        self.repeat,self.repeatone, self.shuffle=False, False,False
        self.player_condition="none"
        self.usersinvc=0


        self.timeidle=0
        self.override=False
        self.channel,self.voice=None,None
        self.song_add_queue, self.songcanadd,self.processsize=Queue(),True,0
        self.lastm:discord.Message=None
        self.messages=[]
        self.internal_message_log=[]
        
        self.processsize=0
        self.FFMPEG_OPTIONS =\
             {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
             "options": "-vn -bufsize 5M -nostats -loglevel 0"}

    async def player_button_call(self, interaction: discord.Interaction, action:str):
        '''Callback for player buttons.'''
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        await self.player_actions(action,editinter=interaction)

    async def countusers(self):
        voice = discord.utils.get(self.bot.voice_clients, guild=self.guild)
        if voice!=None:
            vc=voice.channel
            if vc!=None:
                mem=vc.members
                send=len(mem)/2
        else:
            pass
        

    async def songadd(self):
        if self.song_add_queue.empty()==False:
            print("Adding song.")
            if self.songcanadd:
                self.songcanadd, got= False, False
                try:
                    song=self.song_add_queue.get()
                    got=True
                    await asyncio.gather(
                        asyncio.to_thread(self.musicplayeradd,song)
                    )
                    
                    self.processsize-=1
                    if self.song_add_queue.empty():
                        print("COMPLETED.")
                        if self.get_ctx!=None:
                            mess=await self.get_ctx.send("All songs have been processed.")
                            self.bot.schedule_for_deletion(mess,20)
                except:
                    if got: self.processsize-=1
                    print("PROCESSING ERROR")
                self.songcanadd=True
        if self.internal_message_log:
            front=self.internal_message_log.pop()
            embed=self.get_music_embed('wham',front)
            mess=await self.get_ctx.send(embed=embed)
            


    async def autodisconnect(self):
        
        voice = discord.utils.get(self.bot.voice_clients, guild=self.guild)
        if voice==None:
            return False
        if voice.is_connected():
            if voice.channel!=None:
                if len(voice.channel.members)<=1:
                    self.timeidle+=1
                    print(self.timeidle)
                    if self.timeidle>=120:
                        if self.channel!=None:
                            await self.send_message_internal(self.channel,"disconnected",
                            f"I'm leaving {voice.channel.name} now because I'm the only one in it.")
                        await voice.disconnect()
                        return True
                else:
                    self.timeidle=0
        else:
            pass
        return False


    def reset(self):
        self.songs, self.songhist,self.current= [], [],None
        self.repeat,self.shuffle=False, False
        self.lastm=None
    
    async def setvoiceandctx(self,interaction: discord.Interaction):
        self.channel,self.voice=None,None
        try:
            ctx: commands.Context = await self.bot.get_context(interaction)
            self.voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
            self.channel=ctx.channel
        except:
            self.channel,self.voice=None,None

    async def send_message_internal(self, ctx, title, desc,  editinter: discord.Interaction=None):
        """private send message command."""
        embed=self.get_music_embed(title,desc)
        if editinter==None:
            if self.lastm!=None:
                await self.lastm.delete()
            mymess=self.messages.copy()
            for i in mymess:
                await i.delete()
            m=await ctx.send(embed=embed)
            self.lastm=m
            self.messages=[]
            self.messages.append(m)
        else:
            await editinter.edit_original_response(embed=embed)

    async def send_message(self, ctx_to_try, title, desc,  editinter: discord.Interaction=None):
        """if exception, try stored."""
        try:
            await self.send_message_internal(ctx_to_try,title,desc,editinter)
        except:
            if self.channel!=None:
                await self.send_message_internal(self.channel,title,desc,None)
            else:
                print("Music player never set a voice and channel!")

    async def play(self, ctx, editinter: discord.Interaction=None):
        '''Start playing a song.'''
        voice=self.voice
        if self.current==None:
            self.player_condition="play"
            await self.play_song(ctx)
        else:
            if voice.is_paused():
                self.player_condition="play"
                self.current.resume()
                voice.resume()
                data = self.current
                await self.send_message(ctx, "Resume", f"{data.title} is resuming!",editinter)
            else:
                data = self.current
                await self.send_message(ctx, "Resume", f"{data.title} is already playing!",editinter)
                
    async def stop(self,ctx,editinter:discord.Interaction=None):
        if self.current!=None:
            self.current.stop()
            self.player_condition="stop"
            self.voice.stop()
            if self.repeat:
                self.songs.append(self.current)
            self.current=None
            await self.send_message(ctx, "Stop", f"The player has been stopped.",editinter)

    async def pause(self,ctx,editinter:discord.Interaction=None):
        if self.current!=None:
            if self.voice.is_playing():
                self.voice.pause()
                if not self.override:
                    if self.current:
                        self.current.pause()
                    self.player_condition="pause"
                    await self.send_message(ctx, "Pause", \
                    f"I have paused {self.current.title}!",editinter)
            else: await self.send_message(ctx, "Not playing", "There isn't a song playing right now.",editinter)
        else: await self.send_message(ctx, "Not playing", "There isn't a song playing right now.",editinter)

    async def next(self,ctx,editinter,case="notauto"):
        
        if self.repeatone and case=="auto":
            if self.current!=None: self.songs.insert(0,self.current)
        elif self.repeat:
            if self.current!=None:
                self.current.stop()
                self.songs.append(self.current)
        elif self.current!=None:
            self.current.stop()
            if len(self.songhist)>=16: self.songhist.pop(0)
            self.songhist.append(self.current)
        
        if self.songs: await self.play_song(ctx)
        else:
            if self.current!=None:
                self.current.stop()
                self.current=None
            await self.send_message(ctx, "Empty Playlist", \
                "My playlist is expended, so I can't go to a new song.",editinter)
            self.bot.remove_act("MusicPlay")
            self.player_condition="none"

    async def back(self,ctx,editinter):
        if self.current!=None:
            self.songs.insert(0,self.current)
        if self.repeat:
            back=self.songs.pop()
            self.songs.insert(0,back)
        else:
            if self.songhist:
                torepeat=self.songhist.pop()
                self.songs.insert(0,torepeat)
        if self.songs: await self.play_song(ctx)
        else: 
            await self.send_message(ctx, "Empty Playlist", \
                "There's nothing to go back to!",editinter)
            self.player_condition="none"

    async def player_actions(self, action="", ctxmode=None, editinter: discord.Interaction=None):
        """Dispatch a player action based on action.
        action=[play,stop,pause,next,auto_next]
         ctxmode: command context if available."""
        ctx, voice=self.channel, self.voice
        if ctxmode: ctx=ctxmode
        if self.override!=True:
            if action=="play":
                await self.play(ctx,editinter)
            if action=="stop":
                await self.stop(ctx,editinter)
            if action=="pause":
                await self.pause(ctx,editinter)
            if action=="next":
                await self.next(ctx,editinter)
            if action=="back":
                await self.back(ctx,editinter)
            if action=="auto_next":
                if self.player_condition in ["none","play"]:
                    await self.next(ctx,editinter,case="auto")
        if action=="auto_over":
            self.override=False
            if self.player_condition in ["none","play"]:
                await self.next(ctx,editinter,case="auto")
    
    
    async def playlist_actions(self,action, param=None):
        """add has param AudioContainer, add_url has param url, removespot has param int"""
        if action=="add": #param is type AudioContainer, add to playlist and shuffle if shuffle is on.
            if param:
                #logger.info("adding song...")
                song=param;
                self.songs.append(song)
                if self.shuffle: random.shuffle(self.songs)
                return song
        elif action=="add_url": #param is url to be added.
            if param:
                url,author=param
                song=AudioContainer(url,author.name)
                song.get_song()
                
                if song.state=="Error":
                    print("error")
                    if self.channel!=None:
                        await self.send_message(self.channel,str(song.error_value), desc="Error...")
                    await self.bot.send_error(song.error_value,"Adding URL.")
                    return None

                res=await self.playlist_actions("add",song)
                return res
        elif action=="removespot": #Remove a song from spot in playlist.
            if param:
                spot=param
                if spot<0 or spot>=len(self.songs):
                   return "ERR!&outofrange&ERR!"
                removedsong=self.songs.pop(spot)
                return removedsong
        elif action=="jumpto": #Remove a song from spot in playlist.
            if param:
                spot=param
                if spot<0 or spot>=len(self.songs):
                   return "ERR!&outofrange&ERR!"
                removedsong=self.songs.pop(spot)
                self.songs.insert(0,removedsong)
                return removedsong
        elif action=="shuffle": #Shuffle the playlist once.
            random.shuffle(self.songs)
            return "done"
        elif action=="clear":# Clear the playlist.
            await self.player_actions("stop")
            if self.songs:
                self.songs, self.current = [], None
                return 'done'
            else: return 'emptyalready'
        return "Playlist Command Error"

    async def play_song(self,ctxmode:Union[discord.TextChannel,commands.Context]):
        '''This function starts playback of the current song.'''
        voice,ctx = self.voice,ctxmode  #discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if self.songs:
            self.current = self.songs.pop(0)
            if self.current.state!="Ok":
                self.current.get_song()
                if self.current.state=="Error":
                    print("error")
                    await self.send_message(ctx,str(song.error_value))
                    await self.bot.send_error(self.error_value,"Adding URL.")
                    self.current=None
                    asyncio.run_coroutine_threadsafe(self.player_actions("auto_next"), self.bot.loop)
                    return
            song = self.current
            if voice.is_playing():
                voice.pause()
            song.playing=True
            aud=discord.FFmpegPCMAudio(song.source, **self.FFMPEG_OPTIONS)
            await asyncio.sleep(0.25)
            voice.play(aud,after=lambda e: self.bot.schedule_for_post(ctx.channel, "Error in playback: "+str(e)) if e else  asyncio.run_coroutine_threadsafe(self.player_actions("auto_next"), self.bot.loop))
            voice.is_playing()
            self.bot.add_act("MusicPlay",f"{song.title}",discord.ActivityType.listening)
            await self.send_message(ctx,"play",f"**{song.title}** is now playing.  " )

    async def play_song_override(self,ctxmode:Union[discord.TextChannel,commands.Context],override):
        '''This function starts playback of the current song overridding another..'''
        voice,ctx = self.voice,ctxmode  #discord.utils.get(self.bot.voice_clients, guild=interaction.guild)

        if self.current!=None:
            self.current.stop()
            self.songs.insert(0,self.current)
            self.current=None

        song = self.current
        if voice.is_playing():
            voice.pause()
        
        aud=discord.FFmpegPCMAudio(override, **self.FFMPEG_OPTIONS)
        voice.play(aud,after=lambda e: self.bot.schedule_for_post(ctx.channel, "Error in playback: "+str(e)) if e else asyncio.run_coroutine_threadsafe(self.player_actions("auto_over"), self.bot.loop))

    def musicplayeradd(self,song:AudioContainer):
        #Get song, and add to queue.  BLOCKING OPERATION.
        song.get_song()        
        if song.state=="Error":
            
            self.internal_message_log.append(f"I'm so sorry, {song.title} gave me a weird error: {str(song.error_value)}")
        elif song.state=="Ok": 
            self.songs.append(song)

    def get_music_embed(self, title: str, description: str):
        """Format a status embed and return"""
        embed=discord.Embed(title="", description=description,color=Colour(0x68ff72))
        myname=AssetLookup.get_asset("name")
        myicon=AssetLookup.get_asset("embed_icon")
        embed.set_author(name=f"{myname}'s music player.",\
            icon_url=myicon)
        processing= ""
        con=""
        plistc=""
        if self.player_condition=="play":con="Playing Song."
        elif self.player_condition=="pause":con="Player is Paused."
        elif self.player_condition=="stop":con="Player Stopped."
        if self.repeat: plistc=" Repeat is on."
        elif self.repeatone:plistc=" Repeat One is On."
        if self.processsize>0: processing=f" Processing { self.processsize} songs."
        embed.set_footer(text=f"{con}{plistc}{processing}")

        if self.current!=None:
            song=self.current
            title,url,duration=song.title,song.url,seconds_to_time_stamp(song.duration)
            timeat=seconds_to_time_stamp(song.gettime())
            fieldval=f"{title}\n [{url}]({url})\n{timeat}/{duration}\nRequested by: {song.requested_by}"
            inline=True
            if len(title)>=32: inline=False
            embed.add_field(name="Now Playing",value=fieldval, inline=inline)
        if self.songs:
            duration=0.0
            for i in self.songs:
                duration+=i.duration
            titles,length=[],len(self.songs)
            for i in self.songs[0:3]:
                s=f"•[{i.title}]({i.url})-{i.get_timestamp()}"
                titles.append(s)
            if length>3: titles.append(f"...and {length-3} more.")
            titles.append(seconds_to_time_string(duration))
            res="\n".join(titles)
            embed.add_field(name="Playlist View",value=res,inline=True)
        if self.voice!=None:
            voicelat="{:.4f}".format(self.voice.latency)
            avglat="{:.4f}".format(self.voice.average_latency)
            voice_status=f"{self.voice.endpoint},latency:{voicelat},average_latency:{avglat}"
            embed.add_field(name="VOICE STATUS:",value=voice_status,inline=True)
        return embed
    
