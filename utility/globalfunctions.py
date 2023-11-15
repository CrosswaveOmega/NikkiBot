import os
import re
import discord
from io import BytesIO
from PIL import Image, ImageDraw


from datetime import datetime, timedelta

from discord.ext import commands, tasks

from discord import Webhook, ui
import site
import gui
from discord.utils import escape_markdown

def split_string_with_code_blocks(input_str, max_length,oncode=False):
    tosplitby = [
    # First, try to split along Markdown headings (starting with level 2)
    "\n#{1,6} ",
    # Note the alternative syntax for headings (below) is not handled here
    # Heading level 2
    # ---------------
    
    # Horizontal lines
    "\n\\*\\*\\*+\n",
    "\n---+\n",
    "\n___+\n",
    " #{1,6} ",
    # Note that this splitter doesn't handle horizontal lines defined
    # by *three or more* of ***, ---, or ___, but this is not handled
    "\n\n",
    "\n",
    " ",
    "",
    ]
    if len(input_str) <= max_length:
        return [input_str]

    # Prioritize code block delimiters
    code_block_delimiters = ["```"]
    for code_block_delimiter in code_block_delimiters:
        if code_block_delimiter in input_str:
            parts = input_str.split(code_block_delimiter, 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                # Recursively split the second part and concatenate the results
                if oncode==False:                    
                    return [parts[0]] + split_string_with_code_blocks(code_block_delimiter+parts[1], max_length,oncode=not oncode)
                return [parts[0]+code_block_delimiter] + split_string_with_code_blocks(parts[1], max_length,oncode=not oncode)

    # If no code block delimiter is found, use the regular delimiters
    for separator in tosplitby:
        parts = input_str.split(separator, 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            return [parts[0]] + split_string_with_code_blocks(parts[1], max_length,oncode=oncode)

    # If no suitable separator is found, split at the max length
    return [input_str[:max_length]] + split_string_with_code_blocks(input_str[max_length:], max_length,oncode=oncode)


def replace_working_directory(string):
    """This function is for replacing the current working directory with a shorthand"""
    cwd = os.getcwd()  # Replace backslashes for regex

    parent_dir = os.path.dirname(cwd)
    replaced_string = string
    for rawsite in site.getsitepackages():
        sites = os.path.dirname(rawsite)
        replaced_string = re.sub(re.escape(sites), "site", string, flags=re.IGNORECASE)

    replaced_string = re.sub(
        re.escape(parent_dir), "..", replaced_string, flags=re.IGNORECASE
    )

    return escape_markdown(replaced_string)


def filter_trace_stack(stack):
    """This function is for filtering call stacks so that ONLY the trace related to code files is shown"""
    cwd = os.getcwd()  # Replace backslashes for regex
    newlines = []

    parent_dir = os.path.dirname(cwd)
    for line in stack:
        if parent_dir.upper() in line.upper().strip() and not ".venv" in line.strip():
            newlines.append(line)
    replaced_string = "\n".join(newlines)

    return escape_markdown(replaced_string)


"""Utility functions here to assist."""


def the_string_numerizer(num, thestring, comma=False, force=False, have_s=True):
    if num > 0 or force:
        retstr = "{:.2f} {}".format(num, thestring)
        if num > 1 and have_s:
            retstr = retstr + "s"
        if comma == True:
            retstr += ", "
        return retstr
    return ""


def seconds_to_time_string(seconds_start):
    """return string of days, hours, minutes, and seconds"""
    return_string = ""
    seconds = seconds_start % 60
    minutes_r = (seconds_start - seconds) // 60
    minutes = minutes_r % 60
    hours_r = (minutes_r - minutes) // 60
    hours = hours_r % 24
    days = (hours_r - hours) // 24

    retme = "{}{}{}{}".format(
        the_string_numerizer(days, "day", True),
        the_string_numerizer(hours, "hour", True),
        the_string_numerizer(minutes, "minute", True),
        the_string_numerizer(seconds, "second", force=True),
    )
    return retme


def seconds_to_time_stamp(seconds_init):
    """return string of d:h:m:s"""
    return_string = ""
    seconds_start = int(round(seconds_init))
    seconds = seconds_start % 60
    minutes_r = (seconds_start - seconds) // 60
    minutes = minutes_r % 60
    hours_r = (minutes_r - minutes) // 60
    hours = hours_r % 24
    if hours > 1:
        return_string += "{:02d}:".format(hours)
    return_string += "{:02d}:{:02d}".format(minutes, seconds)
    return return_string


async def get_server_icon_color(guild: discord.Guild) -> str:
    # Get the server's icon
    if not guild.icon:
        return 0xFFFFFF
    icon_bytes = await guild.icon.read()
    icon_image = Image.open(BytesIO(icon_bytes))

    # Resize the image to 1x1 and get the most visible average color
    icon_image = icon_image.resize((1, 1))
    icon_color = icon_image.getpixel((0, 0))

    # Convert the color to hex format
    hex_color = "{:02x}{:02x}{:02x}".format(icon_color[0], icon_color[1], icon_color[2])
    hex = int(hex_color, 16)
    return hex


if __name__ == "__main__":  # testing
    gui.gprint(seconds_to_time_string(130))
