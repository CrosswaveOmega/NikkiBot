import gui
import asyncio
import datetime
import os
import random
from typing import Any, Callable, List
import urllib 
import discord
import subprocess
import re
import logging

import yt_dlp # type: ignore
import itertools
import json
from utility import MessageTemplates, seconds_to_time_string, seconds_to_time_stamp
import mutagen
logs=logging.getLogger("TCLogger")

def speciallistsplitter(objects:List[Any], resetdata:Callable, splitcond:Callable,transformation:Callable, addtransformation:Callable):
    '''Used in MusicCog.  '''
    currlist=[]
    current=resetdata()
    for preobj in objects:
        if splitcond(current,preobj):
            trans=transformation(current)
            currlist.append(trans)
            current=resetdata(current)
        current=addtransformation(current,preobj)
    trans=transformation(current)
    currlist.append(trans)
    return currlist


class AudioContainer():
    """This class is for containing data related to playing audio."""
    def __init__(self, url,requested_by:str="Unknown"):
        info={}

        self.state="uninit"
        self.error_value=None
        
        self.playing=False
        self.query=url
        self.url="N/A"
        self.requested_by=requested_by
        self.title="TITLE UNRETRIEVED"
        self.duration, self.timeat=0,0
        self.type="stream"
        self.json_dict={}
        self.thumbnail=None
        self.started_at:datetime.datetime=discord.utils.utcnow()
        self.seekerspot=0.0
        self.source=None
    

    def get_song_youtube(self,search=False):
        '''Get a song from a youtube url.'''
        info={}
        options={"format": "bestaudio", "noplaylist": "True", 'youtube_include_dash_manifest': False, 'format_sort':["hasaud"]}
        with yt_dlp.YoutubeDL(options) as ydl:
            res=None
            if search:  res = ydl.extract_info(f"ytsearch:{self.query}", download=False)
            else:       res = ydl.extract_info(f"{self.query}", download=False)
            if 'entries' in res:          # a playlist or a list of videos
                info = res['entries'][0]
            else:                         # Just a video
                info = res
        
        dump=json.dumps(info, indent=3, sort_keys=True)
        logs.info(dump)
        self.json_dict=info
        self.title, self.duration,self.url= info["title"], info["duration"], info["webpage_url"]
        self.thumbnail=info['thumbnail']
        self.source=info["url"]
        gui.gprint(self.source)
        self.state="Ok"

    def get_song_soundcloud(self):
        '''Get a song from a soundcloud url.'''
        info={}
        options={"format": "bestaudio","noplaylist": "True",'format_sort':["hasaud"]}
        with yt_dlp.YoutubeDL(options) as ydl:
            res = ydl.extract_info(f"{self.url}", download=False)
            if 'entries' in res:          # a playlist or a list of videos
                info = res['entries'][0]
            else:                         # Just a video
                info = res
        self.json_dict=info
        dump=json.dumps(self.json_dict, indent=3, sort_keys=True)
        logs.info(dump)
        self.title, self.duration,self.url= info["title"], info["duration"], info["webpage_url"]
        self.source=info["url"]
        self.state="Ok"

    def get_song_remote_file(self):
        '''Get a song from a file url.'''
        info={}
        options={"format": "bestaudio","noplaylist": "True",'format_sort':["hasaud"]}
        
        duration_cmd = "ffprobe -i "+self.query+" -show_format -v quiet"
        output = subprocess.check_output(duration_cmd, shell=True, stderr=subprocess.STDOUT).decode("utf-8")
        
        # Find the duration of the audio stream from the ffprobe output
        duration_match = re.search(r"duration=([\d\.]+)", output)
        total_length = int(round(float(duration_match.group(1))))
        gui.gprint("Total Length: "+str(total_length) +" seconds")
        self.title, self.duration,self.url= "Your Song", total_length, self.query
        mdata=mutagen.File(self.query)
        if mdata:
            self.title=mdata.get('title')
        self.source=self.query
        self.state="Ok"
    def get_song_local_file(self):
        '''Get a song from a file url.'''
        info={}
        options={"format": "bestaudio","noplaylist": "True",'format_sort':["hasaud"]}
        

        directory_name = "saveData/music"
        file_name=self.query.replace("local:","")
        # Check if the directory already exists
        if not os.path.exists(directory_name):
            # If it doesn't exist, create it
            os.makedirs(directory_name)
        # Check if the file exists in the directory
        file_path = os.path.join(directory_name, file_name)
        if os.path.exists(file_path):
            pass
        else:
             # Select a random file from the directory
            all_files = os.listdir(directory_name)
            random_file = random.choice(all_files)
            file_path = os.path.join(directory_name, random_file)
            gui.gprint("File not found. Using random file:", random_file)

        gui.gprint("File found at:", file_path)
        # Find the duration of the audio stream from the ffprobe output
        duration_cmd = "ffprobe -i "+file_path+" -show_format -v quiet"
        output = subprocess.check_output(duration_cmd, shell=True, stderr=subprocess.STDOUT).decode("utf-8")
        duration_match = re.search(r"duration=([\d\.]+)", output)
        total_length = int(round(float(duration_match.group(1))))
        gui.gprint("Total Length: "+str(total_length) +" seconds")
        mdata=mutagen.File(file_path)
        self.title, self.duration,self.url= "Your Song", total_length, "./"+file_path
        self.source="./"+file_path
        if mdata:
            self.title=mdata.get('title')
        self.type='file'
        self.state="Ok"

    def is_audio_link(self, link):
        regex = r'.*\.(mp3|wav|ogg|aac|m4a|flac|wma|alac|ape|opus|webm|amr|pcm|aiff|au|raw|ac3|eac3|dts|flv|mkv|mka|mov|avi|mpg|mpeg)$'
        if re.match(regex, link):
            return True
        else:
            return False


    def get_song(self):
        '''Attempt to retrieve a song '''
        try:
            if "youtu" in self.query: #It's a youtube link 
                self.get_song_youtube()
            elif "soundcloud" in self.query: #It's a soundcloud Link
                self.get_song_soundcloud()
            elif 'discordapp' in self.query:
                self.get_song_remote_file()
            elif 'local:' in self.query:
                self.get_song_local_file()
            elif self.is_audio_link(self.query):
                self.get_song_remote_file()

            else: #No idea what it is, do a search.
                self.get_song_youtube(search=True)

        except Exception as e:
            self.state="Error"
            self.error_value=e

    def start(self):
        #start playing a music track.
        self.timeat,self.started_at,self.playing=0,discord.utils.utcnow(),True
    
    def pause(self):
        timebetween=discord.utils.utcnow()-self.started_at
        sec=timebetween.total_seconds()
        self.timeat,self.playing=self.timeat+sec,False
    def stop(self):
        self.timeat,self.started_at,self.playing=0,discord.utils.utcnow(),False
    def resume(self):        
        self.started_at,self.playing=discord.utils.utcnow(),True
    def gettime(self):
        timeat=int(self.timeat)
        if self.playing:
            timeat=int(self.timeat+(discord.utils.utcnow()-self.started_at).total_seconds())
            gui.gprint(timeat)
        return timeat

    def get_timestamp(self):
        return seconds_to_time_stamp(self.duration)

    def to_status_string(self):
        title,url,duration=self.title,self.url,seconds_to_time_stamp(self.duration)
        timeat=seconds_to_time_stamp(self.gettime())
        fieldval=f"{title}\n[{url}]({url})\n{timeat}/{duration}\nRequested by: {self.requested_by}"
        inline=True
        if len(title)>=32: inline=False
    def to_dict(self):
        toreturn={}
        toreturn["title"]=self.title
        toreturn["url"]=self.url
        return toreturn
    def link_markdown(self):
        return f"[{self.title}]({self.url})"
    def to_display_dict(self):
        v={"title":f"[{self.title}]({self.url})","duration":seconds_to_time_string(self.duration), \
        "remaining":seconds_to_time_string(self.duration-self.seekerspot),"requested_by":self.requested_by}
        return v

def url_basename(url):
    path = urllib.parse.urlparse(url).path
    return path.strip('/').split('/')[-1]

async def special_playlist_download(bot, ctx, ie_result):
    ##This was included because downloading from the playlist blocked.
    result_type = ie_result.get('_type', 'video')
    if result_type in ('playlist', 'multi_video'):
        # We process each entry in the playlist
        playlist = ie_result.get('title') or ie_result.get('id')
        playlist_results = []

        playliststart = 0
        playlistend = None
        # For backwards compatibility, interpret -1 as whole list
        if playlistend == -1:
            playlistend = None

        playlistitems_str = None
        playlistitems = None

        ie_entries = ie_result['entries']
        if isinstance(ie_entries, list):
            n_all_entries = len(ie_entries)
            if playlistitems:
                entries = [
                    ie_entries[i - 1] for i in playlistitems
                    if -n_all_entries <= i - 1 < n_all_entries]
            else:
                entries = ie_entries[playliststart:playlistend]
            n_entries = len(entries)
            gui.gprint('[%s] playlist %s: Collected %d video ids (downloading %d of them)' %
                    (ie_result['extractor'], playlist, n_all_entries, n_entries))

        else:  # iterable
            if playlistitems:
                entry_list = list(ie_entries)
                entries = [entry_list[i - 1] for i in playlistitems]
            else:
                entries = list(itertools.islice(
                    ie_entries, playliststart, playlistend))
            n_entries = len(entries)
        x_forwarded_for = ie_result.get('__x_forwarded_for_ip')

        for i, entry in enumerate(entries, 1):
            if i%50==0:
                gui.gprint('[download] Downloading video %s of %s' % (i, n_entries))
            # This __x_forwarded_for_ip thing is a bit ugly but requires
            # minimal changes
            if x_forwarded_for:
                entry['__x_forwarded_for_ip'] = x_forwarded_for
            extra = {
                'n_entries': n_entries,
                'playlist': playlist,
                'playlist_id': ie_result.get('id'),
                'playlist_title': ie_result.get('title'),
                'playlist_index': i + playliststart,
                'extractor': ie_result['extractor'],
                'webpage_url': ie_result['webpage_url'],
                'webpage_url_basename': url_basename(ie_result['webpage_url']),
                'extractor_key': ie_result['extractor_key'],
            }

            entry_result = entry
            playlist_results.append(entry_result)
        ie_result['entries'] = playlist_results
        # gui.gprint(status,'[download] Finished downloading playlist: %s' % playlist)
        #bot.delete_status_message(status)
        return ie_result
    else:
        # bot.delete_status_message(status)
        return None
