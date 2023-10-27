import discord
from discord.ext import commands, tasks
from .MessageTemplates_EXT import MessageTemplatesMusic
import os
import re


async def connection_check(
    interaction: discord.Interaction, ctx: commands.Context, mode: int = 3
) -> bool:
    """Check if the calling user is connected to a voice channel,
    and check if the bot is not currently connected to their same voice channel.
    Return True if Either of these conditions are satisfied (and the command should not run),
    and False if they are both
    """
    if mode == 3 or mode == 1:
        if isinstance(interaction.user.voice, type(None)) and (mode == 3 or mode == 1):
            await MessageTemplatesMusic.music_msg(
                ctx,
                "You aren't connected",
                "You are not connected to any Voice Channel, I can't do anything.",
            )
            return True
    if mode == 3 or mode == 2:
        if interaction.user.voice.channel != ctx.voice_client.channel and (
            mode == 3 or mode == 2
        ):
            await MessageTemplatesMusic.music_msg(
                ctx, "Not connected", "I'm not connected to your **Voice Channel!**"
            )
            return True
    return False


def get_audio_directory():
    directory_name = "saveData/music"

    # Check if the directory already exists
    if not os.path.exists(directory_name):
        # If it doesn't exist, create it
        os.makedirs(directory_name)
    return directory_name


def get_directory_size():
    total_size = 0
    directory = get_audio_directory()
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            total_size += os.path.getsize(filepath)

    return total_size


def is_url(text: str):
    reg = (
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )
    if re.match(reg, text):
        return True
    else:
        return False
