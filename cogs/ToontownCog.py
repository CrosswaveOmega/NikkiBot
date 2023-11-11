from typing import Literal
import discord
import operator
import io
import json
import aiohttp
import asyncio
import re

# import datetime
from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, MO, TU, WE, TH, FR, SA, SU

from datetime import datetime, time, timedelta
import time
from queue import Queue

from discord.ext import commands, tasks
from discord.utils import find
from discord import Webhook, ui

from discord import app_commands
from discord.app_commands import Choice
from pathlib import Path
from utility import (
    MessageTemplates,
    RRuleView,
    formatutil,
    seconds_to_time_string,
    urltomessage,
)
from utility.embed_paginator import pages_of_embeds
from bot import TCBot, TC_Cog_Mixin, super_context_menu
import gptmod
from database import DatabaseSingleton
from gptfunctionutil import *
import gptmod.error
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
import gui
from .ToontownStuff import (
    get_cog_soup,
    desouper,
    formatembed,
    extract_cheat_soup,
    read_article,
)
from assets import AssetLookup
from sqlitedict import SqliteDict

tattle_prompt = """You are tasked with generating new tattles for enemy characters in a video game called ToonTown Online. Each tattle should be written in the same style as the tattles from Paper Mario. Tattles provide amusing and informative descriptions of the enemy, their abilities, and any other noteworthy characteristics. When provided with information about a new enemy, generate a tattle based on the available information.

Example:

Enemy: Cog Boss - Flunky

Tattle: "That's a Flunky, one of the entry-level Cogs. They're like the foot soldiers of the business world, but with less charm. I heard they work for the higher-ranked Cog Bosses, doing their bidding. Their attacks are as basic as they come, but they can still pack a punch if you're not careful. Keep an eye out for their sales pitch!"

Remember, if you do not have enough information, feel free to provide a short amusing remark based on the information you do have."""

tattle_cheat_prompt = """You are tasked with generating a tattle for an enemy character's special abilities, called cheats, in a video game called ToonTown Online. You will be provided a bulleted list of a single enemy's abilities, and you are to summarize that list into a short, one paragraph 'tattle,'  that is no more than 1014 characters long.  Each tattle should be written in the same style as the tattles from Paper Mario. Tattles provide amusing and informative descriptions of the enemy's abilities, as well as a simple strategy to deal with that foe. When provided with information about a new enemy, generate a tattle based on the available information.

Example:

Enemy: Cog Regional Manager - Rainmaker

Tattle: "Every two rounds, Rainmaker will change the weather to a different phase.  Oil rain will make all toons take 10 damage and heal all cogs for 50 HP. Fog will obscure all data on screen.  Heavy Rain will amplify everyone's damage by 20%.  Storm Cell will drop damaging lightning bolts on your toons.  Moonsoon will only be used when Raimnaker is below 880 HP, prevent you from using Toon Up and Sound Gags, significantly increase her defense, and summon buffed cogs to fight for her side!  When she's at 1 HP, she'll dispell the current weather and her flunkies.  You'll get a special cutscene if you go three turns without attacking her, meaning this is a boss you can spare if you're feeling merciful!"

Remember, if you do not have enough information, feel free to provide a short amusing remark based on the information you do have."""
from gptmod import ChatCreation


async def tattle(bot, tattlewith=""):
    object = ChatCreation(
        model="gpt-3.5-turbo-1106",
        messages=[
            {"role": "system", "content": tattle_prompt},
            {"role": "user", "content": tattlewith},
        ],
    )
    res = await bot.gptapi.callapi(object)
    if res.get("err", False):
        err = res[err]
        error = gptmod.error.GptmodError(err, json_body=res)
        raise error
    result = res["choices"][0]["message"]["content"]
    return result


async def api_get(url, params: dict = {}):
    headers = {"user-agent": "NikkiBot/1.0.0"}
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{url}", params=params, headers=headers, timeout=timeout
            ) as response:
                if response.content_type == "application/json":
                    print(response)
                    result = await response.json()
                    return result
        except (aiohttp.ServerTimeoutError, asyncio.TimeoutError) as e:
            raise e
        except aiohttp.ClientError as e:
            raise e


class ToonTownCog(commands.Cog, TC_Cog_Mixin):
    """For Timers."""

    def __init__(self, bot):
        self.helptext = "For Toontown Corporate Clash Api."
        self.bot = bot
        self.db = SqliteDict("./saveData/toondata.sqlite")
        taglist = []
        for i, v in self.db.items():
            if i != "taglist":
                taglist.append(i)
        self.db.update({"taglist": taglist})

    def cog_unload(self):
        self.db.close()

    async def dbsearch(self, query: str):
        positions = [
            "Operations Analyst",
            "Employee",
            "Field Specialist",
            "Regional Manager",
            "Manager",
            "Contractor",
            "Third Cousin Twice Removed",
            "Boss",
        ]
        dict = self.db.get("directory", None)
        if not dict:
            params = {
                "action": "query",
                "generator": "categorymembers",
                "gcmtitle": "Category:The_Cogs",
                "prop": "categories",
                "cllimit": "max",
                "gcmlimit": "max",
                "format": "json",
            }
            overdata = await api_get(
                "https://toontown-corporate-clash.fandom.com/api.php", params
            )
            pages = []
            for i, v in overdata["query"]["pages"].items():
                print(v.keys())
                call = v["title"].replace(" ", "_")
                params = {
                    "action": "parse",
                    "page": call,
                    "format": "json",
                    "section": "0",
                }
                data = await api_get(
                    "https://toontown-corporate-clash.fandom.com/api.php", params
                )
                try:
                    soup, desoup = desouper(data["parse"]["properties"][0]["*"])
                    desoup["title"] = soup["title1"]

                    desoup["urlname"] = call
                    if desoup["position"][1] in positions:
                        pages.append(desoup)
                except Exception as e:
                    print(call, e)
            self.db.update({"directory": pages})
            self.db.commit()
            dict = self.db["directory"]
        for dictionary in dict:
            if query.lower() in dictionary["title"].lower():
                return dictionary["urlname"]
        return None

    @AILibFunction(
        name="toontown_district",
        description="retrieve all connected toontown districts",
        required=["comment"],
    )
    @LibParam(comment="An interesting, amusing remark.")
    @commands.command(
        name="toontown_districts", description="Get toontown districts", extras={}
    )
    async def toontown_district(
        self, ctx: commands.Context, comment: str = "Here are the districts."
    ):
        # This is an example of a decorated discord.py command.
        bot = ctx.bot
        now = datetime.now()
        result = await api_get("https://corporateclash.net/api/v1/districts.js")
        await ctx.send(
            f"{comment}\nToontown Corporate Clash Districts Count:\n{len(result)}"
        )
        embeds = []
        for data in result:
            # Create an empty embed
            print(data)
            embed = discord.Embed(title=data["name"])
            embed.set_author(name="Toontown Corporate Clash", icon_url=bot.user.avatar)
            # Set the title
            embed.add_field(name="Online", value=data["online"])

            embed.add_field(name="Population", value=data["population"])
            # Set the timestamp from the 'last_update' value
            timestamp = datetime.fromtimestamp(data["last_update"])
            embed.timestamp = timestamp

            embed.add_field(name="Invasion", value=data["invasion_online"])
            # Add fields based on condition

            embed.add_field(name="Cogs Attacking", value=data["cogs_attacking"])
            if data["invasion_online"]:
                embed.add_field(name="Count Defeated", value=data["count_defeated"])
                embed.add_field(name="Count Total", value=data["count_total"])
                embed.add_field(name="Remaining Time", value=data["remaining_time"])

                # Add other fields
            embeds.append(embed)
            if len(embeds) > 10:
                await ctx.send(embeds=embeds)
                embeds = []
        if embeds:
            await ctx.send(embeds=embeds)

    # @AILibFunction(name='cog_data',description='Retrieve data for a cog flunky.', required=['comment'])
    # @LibParam(comment='An interesting, amusing remark.')
    @commands.command(name="tattle", description="extract info for a cog.", extras={})
    async def tattle(self, ctx: commands.Context, cogname: str, force: bool = False):
        webhook_url = AssetLookup.get_asset("stathook")

        bot = ctx.bot
        now = datetime.now()
        search = await self.dbsearch(cogname)
        if search == None:
            return await ctx.send("invalid cog name.")
            return
        cogname = search
        cache = self.db.get(search, None)
        Embed = discord.Embed()
        if cache and not force:
            embed = discord.Embed.from_dict(cache)
        else:
            if await ctx.bot.gptapi.check_oai(ctx):
                return

            cheat_tattle = foe_tattle = ""
            page = cogname.replace(" ", "_")
            soup, desoup, attack_soup, cheat_soup = get_cog_soup(cogname)
            addendum = ""
            for i, v in soup.items():
                addendum += f"{v[0]}: {v[1]}\n"
            tattle_text, header = await read_article(
                url=f"https://toontown-corporate-clash.fandom.com/wiki/{page}"
            )
            foe_tattle = await tattle(ctx.bot, addendum + tattle_text)
            if cheat_soup:
                cheat_list = extract_cheat_soup(cheat_soup)
                summe = "\n".join([f"+ {c}" for c in cheat_list])
                cheat_tattle = await tattle(ctx.bot, tattlewith=summe)
            embed = await formatembed(
                f"https://toontown-corporate-clash.fandom.com/wiki/{page}",
                soup,
                desoup,
                attack_soup,
                cheat_soup,
                foe_tattle,
                cheat_tattle,
            )
            self.db.update({search: embed.to_dict()})
            self.db.commit()
            if webhook_url and False:
                async with aiohttp.ClientSession() as session:
                    webhook = discord.Webhook.from_url(webhook_url, session=session)
                    await webhook.send(embed=embed)
        await ctx.send(embed=embed)


async def setup(bot):
    from .ToontownStuff import setup

    await bot.load_extension(setup.__module__)
    await bot.add_cog(ToonTownCog(bot))


async def teardown(bot):
    from .ToontownStuff import setup

    await bot.unload_extension(setup.__module__)
    await bot.remove_cog("ToonTownCog")
