import gui
import asyncio

import discord
import logging
from discord import app_commands, Embed, Colour
from discord.app_commands import Choice
from discord.ext import commands, tasks
import re
from functools import partial
from queue import Queue
from typing import Any, Literal, Callable, Generator, Generic, IO, Optional, TYPE_CHECKING, Tuple, TypeVar, Union
from bot import TCBot, TC_Cog_Mixin

import yt_dlp # type: ignore
import itertools

from assets import AssetLookup

from utility import seconds_to_time_string, seconds_to_time_stamp

from .AudioPlaybackSub import *
logger=logging.getLogger('discord')


'''This is a music player that can play audio in voice chat'''
    
class MusicCog(commands.Cog,TC_Cog_Mixin):
    def __init__(self, bot:TCBot) -> None:
        self.bot :TCBot = bot
        self.helptext="""A list of music commands."""
        self.last_player_message,self.timeoutcountdown=None,discord.utils.utcnow()
        self.song_add_queue, self.songcanadd=Queue(),True
        self.lock = asyncio.Lock()

        self.get_ctx=None

        self.helpdesc="""
        A list of music commands, created using the parzibot music commands as a template, but are slowly getting re-written into something far more advanced.
        
        ""**Help Commands**\n"
            "**Connect commands**\n"
            " • **/mp musichelp** - The list of Nikki's music commands\n\n"
            " • **/mp connect** - Nikki connects to Voice Channel\n"
            " • **/mp disconnect** - Nikki disconnects from Voice Channel\n\n"
            "**Playing commands**\n"
            "**PLEASE NOTE.  /play CAN NOT ADD SONGS DIRECTLY FROM A YOUTUBE PLAYLIST.  YOU MUST USE /playlistcopy for that.**"
            " • **/mp play** `url` - Play song in Voice Channel, or add song to playlist with given url\n"
            " • **/mp nowplaying** - View the song that is currently playing and show the dashboard.\n"
            " • **/mp pause** - Pause current song in Voice Channel\n"
            " • **/mp resume** - Resume current song in Voice Channel\n"
            " • **/mp repeat** `repeatmode`- Enable/Disable current song repeating\n"
            " • **/mp back** - Enable/Disable current song repeating\n"
            " • **/mp next** - Play next song from Playlist\n\n"
            "**Playlist commands**\n"
            " • **/mp playlist** - Show number of songs and songs titles in Playlist\n"
            " • **/mp playlistadd** `url` - Add song to Playlist\n"
            " • **/mp playlistcopy** `copy` - copy a youtube playlist into Nikki's Playlist\n"
            " • **/mp playlistremove** `index` - remove song from Playlist\n"
            " • **/mp playlistjump** `index` - jump to song at index within Playlist\n"
            " • **/mp playlistclear** - Clear all songs from Playlist\n"
            " • **/mp shuffle** - shuffle the playlist once shuffling"
        """
        self.song_add_processer.start()

    def cog_unload(self):
        self.song_add_processer.cancel()


    @tasks.loop(seconds=0.5)
    async def song_add_processer(self):
        '''Fire every 1/20th of a second, download the data for a song in the queue,
         and add to the playlist.  Also check if it's time to disconnect and remove a musicplayer.'''
        toremove=[]
        for i in MusicManager.all_players():
            await i.countusers()
            await i.songadd()
            await i.edit_current_player()
            removeif=await i.autodisconnect()
            if removeif:
                toremove.append(i.guild)
        for i in toremove: MusicManager.remove_player(i)


    
    
    mp = app_commands.Group(name="mp", description="Music Player Commands")
    @app_commands.command(name="music")
    async def music(self, interaction: discord.Interaction) -> None:
        """global music player group."""
        await interaction.response.send_message("Hello from top level command!", ephemeral=True)
        
    @commands.command(name="musichelpcommand")
    async def musichelpme(self, ctx):  
        '''        Just a placeholder command.         '''
        bot = ctx.bot
        auth = ctx.message.author
        channel = ctx.message.channel
        await channel.send("The music cog is all slash commands, so use /musichelp!")
        
    @mp.command(name="musichelp", description="View the list of Nikki's music commands")
    async def musichelp(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        await MessageTemplatesMusic.music_msg(ctx, "Music Commands", (
            "**Help Commands**\n"
            " • **/mp musichelp** - The list of Nikki's music commands\n\n"
            "**Connect commands**\n"
            " • **/mp connect** - Nikki connects to Voice Channel\n"
            " • **/mp disconnect** - Nikki disconnects from Voice Channel\n\n"
            "**Playing commands**\n"
            "**PLEASE NOTE.  /play CAN NOT ADD SONGS DIRECTLY FROM A YOUTUBE PLAYLIST.  YOU MUST USE /playlistcopy for that.**"
            " • **/mp play** `url` - Play song in Voice Channel, or add song to playlist with given url\n"
            " • **/mp pause** - Pause current song in Voice Channel\n"
            " • **/mp nowplaying** - View the song that is currently playing and show the dashboard.\n"
            " • **/mp resume** - Resume current song in Voice Channel\n"
            " • **/mp repeat** `repeatmode`- Enable/Disable current song repeating\n"
            " • **/mp back** - Enable/Disable current song repeating\n"
            " • **/mp next** - Play next song from Playlist\n\n"
            "**Playlist commands**\n"
            " • **/mp playlist** - Show number of songs and songs titles in Playlist\n"
            " • **/mp playlistadd** `url` - Add song to Playlist\n"
            " • **/mp playlistcopy** `copy` - copy a youtube playlist into Nikki's Playlist\n"
            " • **/mp playlistremove** `index` - remove song from Playlist\n"
            " • **/mp playlistjump** `index` - jump to song at index within Playlist\n"
            " • **/mp playlistclear** - Clear all songs from Playlist\n"
            " • **/mp shuffle** - shuffle the playlist once shuffling"))

    @mp.command(name="connect", description="Nikki connects to Voice Channel")
    async def connect(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx,1):
            return

        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        
        
        if isinstance(voice, type(None)) or not voice.is_connected():
            #Add a music player
            MusicManager.add_player(self.bot,guild)
            await interaction.user.voice.channel.connect()
            await MessageTemplatesMusic.music_msg(ctx, "Connected", "I'm connected to **Voice Channel!**")
            await MusicManager.get(guild).setvoiceandctx(interaction)
        elif interaction.user.voice.channel != ctx.voice_client.channel: await MessageTemplatesMusic.music_msg(ctx, "Connected to another", "I'm connected to another **Voice Channel** already!")
        else: 
            vc_name=voice.channel.name
            await MessageTemplatesMusic.music_msg(ctx, "Already connected", f"I'm already connected to {vc_name}")

    @mp.command(name="disconnect", description="Nikki disconnects from Voice Channel")
    async def disconnect(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild

        if isinstance(interaction.user.voice, type(None)):
            await MessageTemplatesMusic.music_msg(ctx, "You aren't connected", "You're not connected to any Voice Channel...")
            return
        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        
        vc_name=voice.channel.name
        if isinstance(voice.is_connected(), type(None)):
            await MessageTemplatesMusic.music_msg(interaction, "Not connected", f"I'm not connected to {vc_name}")
        elif interaction.user.voice.channel != ctx.voice_client.channel:
            await MessageTemplatesMusic.music_msg(ctx, "Connected to another", "I'm connected to another voice channel at the moment...")
        else:
            await MessageTemplatesMusic.music_msg(ctx, "Disconnected", f"I am now disconnected from {vc_name}, bye-bye!")
            if MusicManager.get(guild)!=None:
                MusicManager.get(guild).reset()
                MusicManager.remove_player(guild)
            await voice.disconnect()
            
    @mp.command(name="reconnect", description="Nikki disconnects and reconnects from Voice Channel")
    async def reconnect(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if isinstance(interaction.user.voice, type(None)):
            await MessageTemplatesMusic.music_msg(ctx, "You aren't connected", "You're not connected to any Voice Channel...")
            return
        
        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        vc_name=voice.channel.name
        if isinstance(voice.is_connected(), type(None)):
             await MessageTemplatesMusic.music_msg(interaction, "Not connected", f"I'm not connected to {vc_name}")
        elif interaction.user.voice.channel != ctx.voice_client.channel:
             await MessageTemplatesMusic.music_msg(ctx, "Connected to another", "I'm connected to another voice channel at the moment...")
        else:
            await MessageTemplatesMusic.music_msg(ctx, "Disconnected", f"I am now disconnected from {vc_name}, bye-bye!")
            MusicManager.get(guild).reset()

            await voice.disconnect()


    


    @mp.command(name="play", description="Play song to Voice Channel.  If you have a valid url, you can add it here.")
    @app_commands.describe(url=" URL to audio (YouTube,Soundcloud).  If it is not a url, then Nikki will use it as a search term.")
    async def play(self, interaction: discord.Interaction, url:str=""):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        if await connection_check(interaction,ctx,1):
            return

        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)

        if isinstance(voice, type(None)) or not voice.is_connected():
            MusicManager.add_player(self.bot,guild)
            await interaction.user.voice.channel.connect()
            await MusicManager.get(guild).setvoiceandctx(interaction)
            await MessageTemplatesMusic.music_msg(ctx, "Connected", f"I'm now connected to {interaction.user.voice.channel.name}!")
            
        elif await connection_check(interaction, ctx, 3):
            await MessageTemplatesMusic.music_msg(ctx, "Connected to another", "I'm connected to another Voice Channel.")
            return

        if MusicManager.get(guild).voice==None or MusicManager.get(guild).channel==None:
            await MusicManager.get(guild).setvoiceandctx(interaction)
        if url:
            attempt=await ctx.send("<a:trianglepointer:1132773635195686924> attempting to add")
            song:AudioContainer=await MusicManager.get(guild).playlist_actions("add_url",(url,ctx.author))
            await attempt.delete()
            if song==None:
                await MusicManager.get(guild).send_message(ctx, 
                "something went wrong...", 
                f"OW!  I hit my head trying to get the **{url}** video, are you sure it's a valid URL?")
                return   
            if MusicManager.get(guild).player_condition!="play":              
                await MusicManager.get(guild).player_actions("play",ctx)
            else:
                length=len(MusicManager.get(guild).songs)
                await MusicManager.get(guild).send_message(ctx, "Play", f"There's already something playing, \
                    so I'll just add {song.link_markdown()} to my playlist at spot{length}.")
        else:
            attempt=await ctx.send("<a:trianglepointer:1132773635195686924> starting player.")
            if len(MusicManager.get(guild).songs)>0:
                await MusicManager.get(guild).player_actions("play",ctx)
                await attempt.delete()
                #await ctx.send("processed", ephemeral=True)
            else:
                await ctx.send("There is nothing available I can play.", ephemeral=True)
                            
    


    @mp.command(name="pause", description="Pause current song in Voice Channel")
    async def pause(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        voice = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        await MusicManager.get(guild).player_actions("pause",ctx)



    async def send_player(self, interaction: discord.Interaction):
        if self.last_player_message!=None:
            await self.last_player_message.delete()
            self.bot.schedule_for_deletion(self.last_player_message)
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        newm=await ctx.send("Player message, will be rendered useless after 3 minutes.",
        view=PlayerButtons(inter=interaction,callback=MusicManager.get(guild)))
        self.last_player_message=newm
    
    @mp.command(name="nowplaying", description="View the song currently playing, and send player buttons.")
    async def now_playing(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        if not MusicManager.get(guild).current:
            await MusicManager.get(guild).send_message(ctx, "No music", "I'm not playing any music right now.")
            #await self.send_player(interaction)
            return
        data = MusicManager.get(guild).current
        await MusicManager.get(guild).send_message(ctx, "Now Playing", f"I am currently playing {data.title}!")
        #await self.send_player(interaction)
        

    @mp.command(name="resume", description="Resume current song in Voice Channel")
    async def resume(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return

        await MusicManager.get(guild).player_actions("play",ctx) #Just a stand in for play.

    

    @mp.command(name="repeat", description="Enable/Disable current song repeating")
    @app_commands.describe(action="Repeat type.")
    async def repeat(self, interaction: discord.Interaction, action: Literal['none','all', 'one']):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        if action=='none':
            MusicManager.get(guild).repeat = False
            MusicManager.get(guild).repeatone = False
            await MusicManager.get(guild).send_message(ctx, "Repeat", "I've turned **repeat** mode off.")
        if action=='all':
            MusicManager.get(guild).repeat = True
            MusicManager.get(guild).repeatone = False
            await MusicManager.get(guild).send_message(ctx, "Repeat", "I've turned **repeat** mode on.")
        if action=='one':
            MusicManager.get(guild).repeat = False
            MusicManager.get(guild).repeatone = True
            await MusicManager.get(guild).send_message(ctx, "Repeat", "I've turned **repeat one** mode on.")
        if MusicManager.get(guild).repeat: pass #await MusicManager.get(guild).send_message(ctx, "Repeat", "I've turned **repeat** mode on.")
        else: await MusicManager.get(guild).send_message(ctx, "Repeat", "I've turned **repeat** mode off.")

    @mp.command(name="next", description="Play next song from Playlist")
    async def next(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        await MusicManager.get(guild).player_actions("next",ctx)

    @mp.command(name="back", description="Play last song.")
    async def back(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        await MusicManager.get(guild).player_actions("back",ctx)
    
    
    
    def make_playlist_embeds(self, interaction):
        """MAKE EMBED LIST BASED ON ALL SONGS IN QUEUE"""
        guild:discord.Guild=interaction.guild
        if MusicManager.get(guild).songs:
            duration=0.0
            processing=MusicManager.get(guild).processsize #Check size of songs still getting the data from.
            pstr=""
            if processing>0:
                pstr=f"{processing}"
            for song in MusicManager.get(guild).songs:  duration+=song.duration
            embeds=[]
            def resetdata(current=None):
                if current==None: return (0,[])
                off, titles=current
                return (off, [])
            def splitcond(current, preobj):
                off, titles=current
                if len(titles)>=10: return True
                return False
            def transform(current):
                off, titles=current
                playlist = ''.join(f'**{idv}:** [{song.title}]({song.url})-{song.duration}\n' for idv, song in titles)
                emb=MusicManager.get(guild).get_music_embed("pl",f"**Playlist**\n{playlist}")
                if pstr: emb.add_field(name="Still Processing",value=f"I'm still processing {pstr} songs!")
                emb.set_footer(text=f"{seconds_to_time_string(duration)}")
                return emb
            def addtransform(current,preobj):
                off, titles=current
                app=(off,preobj)
                titles.append(app)
                off=off+1
                return (off,titles)
            
            embeds=speciallistsplitter(MusicManager.get(guild).songs,resetdata,splitcond,transform,addtransform)
            return embeds
    
    
    @mp.command(name="playlist", description="Show the songs you currently have in your Playlist")
    async def playlist(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return

        if MusicManager.get(guild).songs:
            
            pagecall=await MusicManager.get(guild).playlist_view(interaction)
            #ctx: commands.Context = await self.bot.get_context(interaction.message)
            #pagecall=PlaylistPageContainer(interaction, self) #Page container for playlist
            buttons=PlaylistButtons(callback=pagecall) #buttons for playlist
            last_set=await ctx.send(embed=pagecall.make_embed(),view=buttons)
            

        else: await MessageTemplatesMusic.music_msg(ctx, "Empty Playlist", 
        f"My **playlist** is currently empty, and I'm processing {MusicManager.get(guild).processsize} songs.")

    
    @mp.command(name="playlistadd", description="Add a song or playlist to Playlist")
    @app_commands.describe(url="YouTube Video URL")
    async def playlistadd(self, interaction: discord.Interaction, url: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        ydlops={"extract_flat":"in_playlist","skip_download":True,"forcejson":True}
        with yt_dlp.YoutubeDL(ydlops) as ydl:
            try:
                ie = ydl.extract_info(f"{url}", download=False, process=False)
                result_type = ie.get('_type', 'video')
                if result_type in ('playlist', 'multi_video'):
                    await self.playlistcopy(ctx,url,ie)
                    return
            except yt_dlp.DownloadError as e:
                gui.gprint(e)
            opres=await MusicManager.get(guild).playlist_actions("add_url",(url,ctx.author))
            if opres==None:
                await MessageTemplatesMusic.music_msg(ctx, "something went wrong...", f"I couldn't find the **{url}** video... are you sure it's a valid url?")
                return
            await MessageTemplatesMusic.music_msg(ctx, "Playlist", f"**I added {opres.title}** to my playlist.")

    @mp.command(name="add_server_playlist", description="get all music tracks saved inside one channel.")
    @app_commands.describe(channel="The Discord channel in this server the videos are in.")
    @app_commands.describe(messagecount="Total number of messages in channel to check.  Default is 1000.")
    async def playlistaddchannel(self, interaction: discord.Interaction, channel:discord.TextChannel,messagecount:int=1000):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        def Find(string):
            # findall() has been used
            # with valid conditions for urls in string
            regex = r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))"
            url = re.findall(regex, string)
            return [x[0] for x in url]
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        ydlops={"extract_flat":"in_playlist","skip_download":True,"forcejson":True}
        total=0
        totalMessageDisplayAt=0

        counter,average,adjusted_average=0,0,0
        high,low,timebetween,lastest=0,999,0,0
        tnow=discord.utils.utcnow()
        lastTime, lastSet=tnow,tnow
        timeunsetset=True
        
        await MessageTemplatesMusic.music_msg(ctx, "Playlist", f"Please wait, I'm downloading all your server specific music tracks!")
        stat=self.bot.add_status_message(ctx)
        with yt_dlp.YoutubeDL(ydlops) as ydl:
            e=0
            async for thisMessage in channel.history(limit=messagecount):
                e+=1
                thisTime=discord.utils.utcnow()
                difference=thisTime-lastTime
                diff3=(thisTime-lastSet).total_seconds()
                lastSet=discord.utils.utcnow()
                counter += 1
                value=diff3
                average = average + ((value - average) / min(counter, 1))
                adjusted_average = adjusted_average + ((value - adjusted_average) / min(counter, 200))
                high=max(average, high)
                low=min(average,low)
                    

                    
                if(difference.total_seconds()>2):
                    await stat.updatew(f"Time Elapsed={round((tnow-thisTime).total_seconds(),3)}\nMessages iterated:{e}\nTotal URLs found:{total}.")
                    lastTime=discord.utils.utcnow()

                urls=Find(thisMessage.content)
                for i, item in enumerate(urls):
                    url=item
                    song=AudioContainer(url,thisMessage.author.name)
                    MusicManager.get(ctx.guild).song_add_queue.put(song)
                    MusicManager.get(ctx.guild).processsize+=1
                    total+=1  
        stat.delete()  
        await MusicManager.get(ctx.guild).send_message(ctx, "Playlist", f"I added all {total} tracks to my processing queue! \
            They'll be added to the playlist once I finish downloading the data.")

    @app_commands.command(name="radioadd", description="add a audio file to my radio")
    @app_commands.describe(file="An audio file")
    async def radioadd(self, interaction: discord.Interaction, file: discord.Attachment):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        filesize=round(file.size/1000000,2)
        
        Bytelimit = 25 
        if filesize >= Bytelimit:
            await MessageTemplatesMusic.music_msg(ctx,'filecheck',f"This file is {filesize} megabytes large, my upper limit is 25mb!")
            return
        if round(get_directory_size()/1000000,2)+filesize>512:
            await MessageTemplatesMusic.music_msg(ctx,'filecheck',f"Uploading this file will exceed my radio folder's capacity!")
            return
       
        directory_name=get_audio_directory()
        regex = r'.*\.(mp3|wav|ogg|aac|m4a|flac|wma|alac|ape|opus|webm)$'
        if not re.match(regex, file.filename):
            await MessageTemplatesMusic.music_msg(ctx,'filecheck',f"This is not a valid audio file.")
            return 
        filepath=f"{directory_name}/{file.filename}"
        profile=UserMusicProfile.get_or_new(interaction.user.id)
        if profile.check_existing_upload(filepath):
            await MessageTemplatesMusic.music_msg(ctx,'filecheck',f"This is already uploaded.")
            return
        if profile.check_upload_limit():
            await MessageTemplatesMusic.music_msg(ctx,'filecheck',f"You've hit the upper limit of uploadable songs.")
            return
        profile.add_song(filepath,filesize)
        await file.save(filepath)
        await MessageTemplatesMusic.music_msg(ctx,'filecheck',f"Uploaded {file.filename} to my radio folder!")
        await ctx.bot.get_channel(ctx.bot.error_channel).send(f"Uploaded {file.filename} into the radio folder.")

        
        
        

    
    @mp.command(name="playlistcopy", description="get multiple songs from youtube playlist")
    @app_commands.describe(url="YouTube Playlist URL")
    async def playlistcopier(self, interaction: discord.Interaction, url: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        await self.playlistcopy(ctx,url,None)


    async def playlistcopy(self, ctx, url: str, initial=None):
        await MessageTemplatesMusic.music_msg(
            ctx, 
            "Playlist",
             f"reading the urls from [playlist]({url})",
             delete_after=False,use_author=False
             )

        total=0
        ydlops={"extract_flat":"in_playlist","skip_download":True,"forcejson":True}
        self.get_ctx=ctx.channel
        with yt_dlp.YoutubeDL(ydlops) as ydl:
            internetres=initial
            if internetres==None:
                internetres = ydl.extract_info(f"{url}", download=False, process=False)
            res=await special_playlist_download(self.bot, ctx, internetres)
            stat=self.bot.add_status_message(ctx)
            await stat.updatew(f"Converting Tracks.")   
            if 'entries' in res:
                video = res['entries']
                l=len(video)
                if l>=256:
                    await MessageTemplatesMusic.music_msg(ctx, "something went wrong...", f"...I am not adding {l} songs from this playlist...")
                    return
                for i, item in enumerate(video):
                    url="https://youtu.be/"+item['id']
                    song=AudioContainer(url,ctx.author.name)
                    MusicManager.get(ctx.guild).song_add_queue.put(song)
                    MusicManager.get(ctx.guild).processsize+=1
                    total+=1                   
                stat.delete()
        await MusicManager.get(ctx.guild).send_message(ctx, "Playlist", f"I added all {total} tracks to my processing queue! \
             They'll be added to the playlist once I finish downloading the data.")

        #self.songs.append(song)
        #if self.shuffle: random.shuffle(self.songs)





    @mp.command(name="playlistjump", description="set the song at spot to play next!")
    @app_commands.describe(spot="position of song in playlist.")
    async def playlistjump(self, interaction: discord.Interaction, spot: int):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return

        result=await MusicManager.get(guild).playlist_actions("jumpto",spot)
        
        if result=="ERR!&outofrange&ERR!":
            await MessageTemplatesMusic.music_msg(ctx, "something went wrong...", f"The provided spot is out of range of my playlist!")
            return
        await MessageTemplatesMusic.music_msg(ctx, "Playlist", f"**I moved {result.title}** to the front of my playlist.",result.to_display_dict())


    @mp.command(name="playlistremove", description="Remove song from Playlist")
    @app_commands.describe(spot="position of song in playlist.")
    async def playlistremove(self, interaction: discord.Interaction, spot: int):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return

        result=await MusicManager.get(guild).playlist_actions("removespot",spot)
        
        if result=="ERR!&outofrange&ERR!":
            await MessageTemplatesMusic.music_msg(ctx, "something went wrong...", f"The provided spot is out of range of my playlist!")
            return
        await MessageTemplatesMusic.music_msg(ctx, "Playlist", f"**I removed {result.title}** from my playlist.",result.to_display_dict())


    @mp.command(name="playlistclear", description="Clear all songs from Playlist")
    async def playlistclear(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return

        res=await MusicManager.get(guild).playlist_actions("clear")
        if res=='done':
            await MessageTemplatesMusic.music_msg(ctx, "Clear Playlist", "I cleared out my playlist.")
        else: await MessageTemplatesMusic.music_msg(ctx, "Empty Playlist", "My playlist is already empty.")


    @mp.command(name="shuffle", description="Shuffle all songs in the queue.")
    async def playlistshuffle(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        res=await MusicManager.get(guild).playlist_actions("shuffle")
        if res=="done":
            await MessageTemplatesMusic.music_msg(ctx, "Shuffle", "I've shuffled my playlist!")
        else: await MessageTemplatesMusic.music_msg(ctx, "?",f"{res}")
        
    @mp.command(name="search", description="search cache")
    async def search(self, interaction: discord.Interaction,search:str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        me=await ctx.send('searching... <a:trianglepointer:1132773635195686924>')
        results=MusicJSONMemoryDB.search(search, do_maxsearch=True)
        text="\n".join(f"{e}:{s}" for e, s in enumerate(results))
        if text:
            await me.edit(content=text)

        else:
            await ctx.send("no results.")
    @mp.command(name="myplaylists", description="View a list of your playlists.")
    async def myplaylists(self, interaction: discord.Interaction):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        await ctx.send("coming soon.")
        '''
        profile=UserMusicTable.get_user_profile(id)
        lis=profile.show_playlists()
        splitter=DataSplitTransformer.basicsplit(10)
        def _into_embed(self,results):
            desc="+\n".join(s for s in results)
            embed=discord.Embed(title="Scene List",description=desc)
            return embed
        splitter.transformation=partial(_into_embed,splitter)

        disp=splitter.execute(lis)
        await ctx.send(str(lis))
        
        await pages_of_embeds(ctx, disp)
        '''


    @mp.command(name="playlistsave", description="Save the current playlist.")
    @app_commands.describe(playlistname="Name of playlist to save")
    async def playlistsave(self, interaction: discord.Interaction, playlistname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        await ctx.send("Coming soon.")
        '''
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        
        songs=MusicManager.get(guild).songs;
        list=[]
        for s in songs:
            i=s.to_dict()
            title,url=i["title"],i["url"]
            list.append(s.to_dict())
        author=ctx.author
        id=author.id
        profile=UserMusicTable.get_user_profile(id)
        profile.save_playlist(playlistname,list)

        await MessageTemplatesMusic.music_msg(ctx, "Playlist", f"Saved playlist {playlistname}!")
        '''

    @mp.command(name="playlistload", description="Load a saved playlist.")
    @app_commands.describe(playlistname="Name of playlist to load")
    async def playlistload(self, interaction: discord.Interaction, playlistname: str):
        ctx: commands.Context = await self.bot.get_context(interaction)
        guild:discord.Guild=interaction.guild
        
        await ctx.send("Coming soon.")
        '''
        if await connection_check(interaction,ctx): #if it's true, then it shouldn't run.
            return
        author=ctx.author
       
        profile=UserMusicTable.get_user_profile(author.id)
        playlist=profile.load_playlist(playlistname)
        for i in (playlist):
            title,url=i["title"],i["url"]
            #gui.gprint(f"title:{title},url:{url}")
            song=AudioContainer(url,author.name)
            MusicManager.get(guild).song_add_queue.put(song)
            MusicManager.get(guild).processsize+=1
        await MessageTemplatesMusic.music_msg(ctx, "Playlist", f"Loaded size {len(playlist)} playlist `{playlistname}` into processing queue.  Please wait.")'''

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog()
            
async def setup(bot):
    print(__name__)
    from .AudioPlaybackSub import setup
    await bot.load_extension(setup.__module__)
    await bot.add_cog(MusicCog(bot))



async def teardown(bot):
    
    from .AudioPlaybackSub import setup
    await bot.unload_extension(setup.__module__)
    await bot.remove_cog('MusicCog')
