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
import re
from typing import Union


def split_and_cluster_strings(
    input_string: str, max_cluster_size: int, split_substring: str, length=len
) -> list[str]:
    """
    Split up the input_string by the split_substring
    and group the resulting substrings into
    clusters of about max_cluster_size length.
    Return the list of clusters.

    Args:
    input_string (str): The string to be split and clustered.
    max_cluster_size (int): The preferred maximum length of each cluster.
    split_substring (str): The substring used to split the input_string.

    Returns:
    list[str]: A list of clusters.
    """
    clusters = []
    # There's no reason to split if input is already less than max_cluster_size
    if length(input_string) < max_cluster_size:
        return [input_string]

    split_by = split_substring

    is_regex = isinstance(split_substring, re.Pattern)
    if is_regex:
        result = split_substring.split(input_string)
        substrings = [r for r in result if r]
    else:
        if "%s" not in split_substring:
            split_by = "%s" + split_by
        split_character = split_by.replace("%s", "")

        # Split the input string based on the specified substring
        substrings = input_string.split(split_character)
    # No reason to run the loop if there's less than two
    # strings within the substrings list.  That means
    # it couldn't find anything to split up.
    if len(substrings) < 2:
        return [input_string]

    current_cluster = substrings[0]
    for substring in substrings[1:]:
        if not is_regex:
            new_string = split_by.replace("%s", substring, 1)
        else:
            new_string = substring
        sublength = length(new_string)
        if length(current_cluster) + sublength <= max_cluster_size:
            # Add the substring to the current cluster
            current_cluster += new_string
        else:
            # Adding to the current cluster will exceed the maximum size,
            # So start a new cluster.
            if current_cluster:
                # Don't add to clusters if current_cluster is empty.
                clusters.append(current_cluster)
            current_cluster = ""
            if substring:
                # Don't add to current_cluster if substring is empty.
                # Add the last cluster if not empty.
                current_cluster = new_string
    if current_cluster:
        clusters.append(current_cluster)  # Remove the trailing split_substring

    return clusters


def prioritized_string_split(
    input_string: str,
    substring_split_order: list[Union[str, tuple[str, int]]],
    default_max_len: int = 1024,
    trim=False,
    length=len,
) -> list[str]:
    """
    Segment the input string based on the delimiters specified in `substring_split_order`.
    Then, concatenate these segments to form a sequence of grouped strings,
    ensuring that no cluster surpasses a specified maximum length.
    The maximum length for each cluster addition
    can be individually adjusted along with the list of delimiters.


    Args:
        input_string (str): The string to be split.
        substring_split_order (list[Union[str, tuple[str, int]]]):
            A list of strings or tuples containing
            the delimiters to split by and their max lengths.
            If an argument here is "%s\\n", then the input string will be split by "\\n" and will
            place the relevant substrings in the position given by %s.
        default_max_len (int): The maximum length a string in a cluster may be if not given
            within a specific tuple for that delimiter.
        trim (bool): If True, trim leading and trailing whitespaces in each cluster. Default is False.

    Returns:
        list[str]: A list of clusters containing the split substrings.
    """

    # Initalize new cluster
    current_clusters = [input_string]
    for e, arg in enumerate(substring_split_order):
        if isinstance(arg, str):
            s, max_len = arg, None
        elif isinstance(arg, re.Pattern):
            s, max_len = arg, None
        elif len(arg) == 1:
            s, max_len = arg[0], None
        else:
            s, max_len = arg

        max_len = max_len or default_max_len  # Use default if not specified
        split_substring = s
        new_splits = []

        for cluster in current_clusters:
            result_clusters = split_and_cluster_strings(
                cluster, max_len, split_substring, length=length
            )
            new_splits.extend(result_clusters)
        # for c_num, cluster in enumerate(new_splits):
        #    print(f"Pass {e},  Cluster {c_num + 1}: {len(cluster)}, {len(cluster)}")
        current_clusters = new_splits

    # Optional trimming of leading and trailing whitespaces
    if trim:
        current_clusters = [cluster.strip() for cluster in current_clusters]

    return current_clusters


def split_string_with_code_blocks(input_str, max_length, oncode=False):
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
    symbol = re.escape("```")
    pattern = re.compile(f"({symbol}(?:(?!{symbol}).)+{symbol})")

    splitorder = [pattern, "\n### %s", "%s\n", " %s"]
    fil = prioritized_string_split(input_str, splitorder, default_max_len=max_length)
    return fil
    # Prioritize code block delimiters
    code_block_delimiters = ["```"]
    for code_block_delimiter in code_block_delimiters:
        if code_block_delimiter in input_str:
            parts = input_str.split(code_block_delimiter, 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                # Recursively split the second part and concatenate the results
                if oncode == False:
                    return [parts[0]] + split_string_with_code_blocks(
                        code_block_delimiter + parts[1], max_length, oncode=not oncode
                    )
                return [
                    parts[0] + code_block_delimiter
                ] + split_string_with_code_blocks(
                    parts[1], max_length, oncode=not oncode
                )

    # If no code block delimiter is found, use the regular delimiters
    for separator in tosplitby:
        parts = input_str.split(separator, 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            return [parts[0]] + split_string_with_code_blocks(
                parts[1], max_length, oncode=oncode
            )

    # If no suitable separator is found, split at the max length
    return [input_str[:max_length]] + split_string_with_code_blocks(
        input_str[max_length:], max_length, oncode=oncode
    )


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
