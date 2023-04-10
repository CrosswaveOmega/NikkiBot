import discord
import operator
import asyncio
import csv
from discord.ext import commands, tasks

from discord import Webhook
from pathlib import Path
import json


def urlto_gcm_ids(link=""):
    #Attempt to extract guild, channel, and messageids from url.
    if not isinstance(link, str):
        print("LINK IS NOT A STRING.")
        return None

    linkcontents=link.split('/')

    if not (len(linkcontents)>=7):
        print("LINK IS NOT VALID.")
        return None
    guild_id = int(linkcontents[4])
    channel_id = int(linkcontents[5])
    message_id = int(linkcontents[6])
    return guild_id, channel_id, message_id


async def urltomessage(link="", bot=None):
    if bot==None:
        print("BOT WAS NOT DEFINED.")
        return None
    tup=urlto_gcm_ids(link)
    guild_id, channel_id, message_id=tup
    guild = bot.get_guild(guild_id)
    channel = guild.get_channel(channel_id)
    message = await channel.fetch_message(message_id)
    return message
