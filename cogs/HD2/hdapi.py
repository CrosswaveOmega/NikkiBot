import io
import re
from typing import Literal, List
import aiohttp
import gui
import discord
import asyncio
from PIL import Image, ImageDraw
from discord import app_commands
import numpy as np
from assets import GeoJSONGeometry, GeoJSONFeature

# import datetime
from utility.views import BaseView
from bot import (
    TCBot,
    TC_Cog_Mixin,
)
from discord.ext import commands

api = "https://api.helldivers2.dev/api/v1/"


async def call_api(endpoint):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{api}{endpoint}") as r:
            if r.status == 200:
                js = await r.json()
                await session.close()
                return js


def human_format(num):
    num = float("{:.3g}".format(num))
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    suffixes = ["", "K", "M", "B", "T", "Q", "Qi"]
    return "{}{}".format(
        "{:f}".format(num).rstrip("0").rstrip("."), suffixes[magnitude]
    )
