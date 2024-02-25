from typing import List
import chromadb
import discord
import asyncio
from assets import AssetLookup
import re

# import datetime


from discord.ext import commands

from discord import app_commands
from bot import TC_Cog_Mixin, StatusEditMessage, super_context_menu, TCBot
from .tools import (
    has_url,
    read_and_split_link,
    store_splits,
)
import gptmod
import gptfunctionutil as gptu
import gptmod.error
from database.database_ai import AuditProfile

# I need the readability npm package to work, so
from javascriptasync import require, eval_js
import assets
import gui

from .chromatools import ChromaTools

from googleapiclient.discovery import build  # Import the library

from utility import prioritized_string_split, select_emoji
from utility.embed_paginator import pages_of_embeds


class SourceLinkLoader:
    """
    Manages the loading of links, including checking if they're cached, splitting content,
    and updating or adding entries to the database as necessary.
    """

    def __init__(self, chromac: chromadb.ClientAPI, statusmessage: StatusEditMessage):
        self.chromac = chromac
        self.statmess = statusmessage
        self.current = ""
        pass

    async def load_links(
        self,
        ctx: commands.Context,
        all_links: List[str],
        override: bool = False,
    ):
        """
        Asynchronously loads links, checks for cached documents, and processes the split content.

        Args:
            ctx (commands.Context): The context of the command.
            all_links (List[str]): List of links to be processed.
            override (bool, optional): If True, override cache and process all links. Defaults to False.

        Returns:
            Tuple[int, str]: A tuple containing the count of successfully processed links and a formatted status string.
        """
        if not self.statmess:
            self.statmess = await self.initialize_status_message(ctx)

        if not self.chromac:
            self.chromac = ChromaTools.get_chroma_client()

        self.current, hascount = "", 0
        self.all_link_status = [["pending", link] for link in all_links]

        for link_num, link in enumerate(all_links):
            embed = discord.Embed(
                description=f"google search\n{self.get_status_lines()}"
            )

            has, getres = await self.check_cached_documents(ctx, link, override)

            if has and not override:
                self.current += self.process_cached_link(link_num, link, getres)
                hascount += 1
            else:
                await self.process_uncached_link(ctx, link_num, link, embed)

        return hascount, self.get_status_lines()

    async def initialize_status_message(self, ctx: commands.Context):
        """
        Initializes and sends a status message in the given context.

        Args:
            ctx (commands.Context): The context of the command.

        Returns:
            StatusEditMessage: The object for editing and updating the status message.
        """
        target_message = await ctx.channel.send(
            f"<a:SquareLoading:1143238358303264798> checking returned queries ..."
        )
        return StatusEditMessage(target_message, ctx)

    def get_status_lines(self):
        """
        Generates status lines for all links based on their current processing status.

        Returns:
            str: A formatted string representing the current status of all links.
        """
        return "\n".join(
            [f"{select_emoji(s)} {link}" for s, link in self.all_link_status]
        )

    async def check_cached_documents(self, ctx, link, override):
        """
        Checks if the provided link is already cached, unless overriding is requested.

        Args:
            ctx (commands.Context): The context of the command.
            link (str): The URL to check in the cache.
            override (bool): Flag to indicate whether to ignore the cached result.

        Returns:
            tuple: A tuple where the first element indicates if the link is cached, and the second element is the cached data if any.
        """

        result = await asyncio.to_thread(has_url, link, client=self.chromac)
        has, getres = result
        # Accessing traced results
        # The results object contains information about executed lines, missing lines, and more

        if has and not override:
            for d, me in zip(getres["documents"], getres["metadatas"]):
                if me["source"] != link:
                    raise Exception(
                        "the url in the cache doesn't match the provided url."
                    )
            return True, getres
        return False, None

    def process_cached_link(self, link_num, link, getres):
        """
        Processes a link that was found in the cache.

        Args:
            link_num (int): The index of the link in the list.
            link (str): The URL of the link.
            getres (dict): The cached data of the link.

        Returns:
            str: A formatted string indicating the cached status of the link.
        """
        self.all_link_status[link_num][0] = "skip"
        return f"[Link {link_num}]({link}) has {len(getres['documents'])} cached documents.\n"

    async def process_uncached_link(
        self,
        ctx,
        link_num,
        link,
        embed,
    ):
        """
        Processes a link that was not found in the cache.

        Args:
            ctx (commands.Context): The context of the command.
            link_num (int): The index of the link in the list.
            link (str): The URL of the link.
            embed (discord.Embed): The embed object for display updates.

        """
        try:
            splits, type = await read_and_split_link(ctx.bot, link)
            dbadd = True
            for split in splits:
                for i, m in split.metadata.items():
                    if m is None:
                        split.metadata[i] = "N/A"
                    else:
                        dbadd = True

            if dbadd:
                await self.process_uncached_link_add(link_num, link, splits, embed)

        except Exception as err:
            await self.process_uncached_link_error(ctx, link_num, link, err, embed)

    async def process_uncached_link_add(
        self,
        link_num,
        link,
        splits,
        embed,
    ):
        """
        Adds a link and its splits to the database and updates the status message.

        Args:
            link_num (int): The index of the link in the list.
            link (str): The URL of the link.
            splits (list): The list of splits obtained from the link.
            embed (discord.Embed): The embed object for display updates.

        """
        self.all_link_status[link_num][0] = "add"
        toadd = f"[Link {link_num}]({link}) has {len(splits)} splits.\n"
        self.current += toadd
        embed.description = self.get_status_lines()
        await asyncio.to_thread(store_splits, splits, client=self.chromac)
        await self.statmess.editw(
            min_seconds=5,
            content=f"<a:LetWalkR:1118191001731874856> {self.current}",
            embed=embed,
        )

    async def process_uncached_link_error(self, ctx, link_num, link, err, embed):
        """
        Handles errors encountered during the processing of an uncached link, updating the status message accordingly.

        Args:
            ctx (commands.Context): The context of the command.
            link_num (int): The index of the link in the list.
            link (str): The URL of the link.
            err (Exception): The error encountered.
            embed (discord.Embed): The embed object for display updates.

        """
        self.all_link_status[link_num][0] = "noc"
        self.current += f"{str(err)}"
        await ctx.send(str(err))
        embed.description = self.get_status_lines()
        await self.statmess.editw(
            min_seconds=5,
            content=f"<a:LetWalkR:1118191001731874856> {self.current}",
            embed=embed,
        )
        await ctx.bot.send_error(err)
