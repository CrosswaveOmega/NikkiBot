
import os
import re
import discord
from io import BytesIO
from PIL import Image, ImageDraw


from datetime import datetime, timedelta

from discord.ext import commands, tasks

from discord import Webhook,ui
import site
import gui
from discord.utils import escape_markdown


def replace_working_directory(string):
    '''This function is for replacing the current working directory with a shorthand'''
    cwd = os.getcwd()  # Replace backslashes for regex
    
    parent_dir = os.path.dirname(cwd)
    replaced_string=string
    for rawsite in site.getsitepackages():
        sites = os.path.dirname(rawsite)
        # Use regex to replace all instances of the working directory in the string
        replaced_string = re.sub(re.escape(sites), 'site', string, flags=re.IGNORECASE)
    # Use regex to replace all instances of the working directory in the string
    replaced_string = re.sub(re.escape(parent_dir), '..', replaced_string, flags=re.IGNORECASE)

    return escape_markdown(replaced_string)

def filter_trace_stack(stack):
    '''This function is for filtering call stacks'''
    cwd = os.getcwd()  # Replace backslashes for regex
    print("Call stack:")
    newlines=[]
    
    parent_dir = os.path.dirname(cwd)
    print(cwd)
    print(parent_dir)
    for line in stack:
        print(line)
        #print(line.strip(),print(parent_dir))
        if parent_dir.upper() in line.upper().strip() and not '.venv' in line.strip():
            newlines.append(line) 
            print("AS",line.strip())
    replaced_string="\n".join(newlines)

    return escape_markdown(replaced_string)

'''Utility functions here to assist.'''
'''Utility functions here to assist.'''

def the_string_numerizer(num,thestring,comma=False, force=False, have_s=True):
    if num>0 or force:
        retstr="{:.2f} {}".format(num,thestring)
        if num>1 and have_s:
            retstr=retstr+"s"
        if comma==True:
            retstr+=", "
        return retstr
    return ""

def seconds_to_time_string(seconds_start):
    '''return string of days, hours, minutes, and seconds'''
    return_string=""
    seconds=seconds_start%60
    minutes_r=(seconds_start-seconds)//60
    minutes=minutes_r%60
    hours_r=(minutes_r-minutes)//60
    hours=hours_r%24
    days=(hours_r-hours)//24
    
    retme="{}{}{}{}".format(\
        the_string_numerizer(days,"day",True),\
        the_string_numerizer(hours,"hour",True),\
        the_string_numerizer(minutes,"minute",True),\
        the_string_numerizer(seconds,"second",force=True)
        )
    return retme

def seconds_to_time_stamp(seconds_init):
    '''return string of d:h:m:s'''
    return_string=""
    seconds_start=int(round(seconds_init))
    seconds=seconds_start%60
    minutes_r=(seconds_start-seconds)//60
    minutes=minutes_r%60
    hours_r=(minutes_r-minutes)//60
    hours=hours_r%24
    if hours>1:
        return_string+="{:02d}:".format(hours)
    return_string+="{:02d}:{:02d}".format(minutes,seconds)
    return return_string


async def get_server_icon_color(guild: discord.Guild) -> str:
    # Get the server's icon
    if not guild.icon:
        return 0xffffff
    icon_bytes = await guild.icon.read()
    icon_image = Image.open(BytesIO(icon_bytes))

    # Resize the image to 1x1 and get the most visible average color
    icon_image = icon_image.resize((1, 1))
    icon_color = icon_image.getpixel((0, 0))

    # Convert the color to hex format
    hex_color = "{:02x}{:02x}{:02x}".format(icon_color[0], icon_color[1], icon_color[2])
    hex=int(hex_color,16)
    return hex




if __name__ == "__main__": #testing
    gui.gprint(seconds_to_time_string(130))


