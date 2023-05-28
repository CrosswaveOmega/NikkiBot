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
from utility import  seconds_to_time_string, seconds_to_time_stamp, urltomessage
from utility import PageClassContainer
from .AudioContainer import AudioContainer
from .MusicUtils import connection_check
from .MusicViews import PlayerButtons
from .MusicPlayer_Mixins import PlaylistMixin, PlayerMixin
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

class MusicPlayer(PlaylistMixin, PlayerMixin):
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
        self.setup_actions()
        self.setup_playlist_actions()
        
        self.processsize=0
        self.FFMPEG_OPTIONS =\
             {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
             "options": "-vn -bufsize 5M -nostats -loglevel 0"}
        self.FFMPEG_FILEOPTIONS =\
             {"options": "-vn -loglevel 0"}


    async def player_button_call(self, interaction:discord.Interaction, action:str):
        '''Callback for player buttons.'''
        ctx: commands.Context = await self.bot.get_context(interaction.message)
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
            if self.channel:
                mess=await self.channel.send(embed=embed)
            


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
                        self.bot.remove_act("MusicPlay")
                        return True
                else:
                    self.timeidle=0
        else:
            pass
        return False


    def reset(self):
        '''reset the player.'''
        self.songs, self.songhist,self.current= [], [],None
        self.repeat,self.shuffle=False, False
        self.lastm=None
    
    async def setvoiceandctx(self,interaction: discord.Interaction):
        '''Set an internal Voice Client and Message Channel from the passed in interaction.'''
        self.channel,self.voice=None,None
        try:
            ctx: commands.Context = await self.bot.get_context(interaction)
            self.voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
            self.channel=ctx.channel
        except:
            self.channel,self.voice=None,None

    async def send_message_internal(self, ctx, title, desc,  editinter: discord.Interaction=None):
        """Send or edit a player message."""
        embed=self.get_music_embed(title,desc)
        if editinter==None:
            if self.lastm!=None:
                try:
                    await self.lastm.delete()
                except Exception as e:
                    print(e)
                    try:
                        jurl=self.lastm.jump_url
                        mep=await urltomessage(jurl,self.bot,partial=True)
                        await mep.delete()
                    except Exception as ep:
                        print(ep)
            #mymess=self.messages.copy()
            #for i in mymess:   await i.delete()
            m=await ctx.send(embed=embed, view=PlayerButtons(
                callback=self
            ))
            self.lastm=m
            #self.messages=[]
            #self.messages.append(m)
        else:
            await editinter.edit_original_response(embed=embed)

    async def send_message(self, ctx_to_try:commands.Context, title:str, desc:str,  editinter: discord.Interaction=None):
        """Send a message through the ctx_to_try"""
        try:
            await self.send_message_internal(ctx_to_try,title,desc,editinter)
        except:
            if self.channel!=None:
                await self.send_message_internal(self.channel,title,desc,None)
            else:
                print("Music player never set a voice and channel!")


    async def play_song(self,ctxmode:Union[discord.TextChannel,commands.Context]):
        '''Start playback of the current song.'''
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
            
            aud=discord.FFmpegPCMAudio(song.source, **self.FFMPEG_OPTIONS)
            if song.type=='file':
                aud=discord.FFmpegPCMAudio(song.source, **self.FFMPEG_FILEOPTIONS)
            await asyncio.sleep(0.25)
            song.start()
            voice.play(aud,
                       after=lambda e: self.bot.schedule_for_post(ctx.channel, "Error in playback: "+str(e)) if e else  asyncio.run_coroutine_threadsafe(self.player_actions("auto_next"), 
                        self.bot.loop))
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
        '''Get song, and add to queue.  BLOCKING OPERATION.'''
        song.get_song()        
        if song.state=="Error":
            self.internal_message_log.append(f"I'm so sorry, {song.title} gave me a weird error: {str(song.error_value)}")
        elif song.state=="Ok": 
            self.songs.append(song)

    def get_music_embed(self, title: str, description: str)->discord.Embed:
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
            fieldval=f"{title}\n {url} \n{timeat}/{duration}\nRequested by: {song.requested_by}"
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
            voice_status=f"{self.voice.endpoint},\nlatency:{voicelat},\navg_latency:{avglat}"
            embed.add_field(name="VOICE STATUS:",value=voice_status,inline=True)
        return embed
    
