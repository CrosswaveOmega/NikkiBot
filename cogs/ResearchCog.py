import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple

print("Discord import")
import discord
import gptfunctionutil.functionlib as gptum
from discord import app_commands
from discord.ext import commands

print("Discord import")
from gptfunctionutil import (
    AILibFunction,
    LibParam,
)

print("Discord import")
from javascriptasync import JSContext

import gptmod
import gui
import assetloader
from assetloader import AssetLookup
from bot import StatusEditMessage, TC_Cog_Mixin, TCBot, super_context_menu
from database.database_ai import AuditProfile
from utility import prioritized_string_split
from utility.embed_paginator import pages_of_embeds
import importlib

print("Importing agent.")
import cogs.ResearchAgent as ra

print("Research agent done.")
from .ResearchAgent.views import *


SERVER_ONLY_ERROR = "This command may only be used in a guild."
INVALID_SERVER_ERROR = (
    "I'm sorry, but the research system is unavailable in this server."
)


async def check_ai_rate(ctx):
    serverrep, userrep = AuditProfile.get_or_new(ctx.guild, ctx.author)
    serverrep.checktime()
    userrep.checktime()
    ok, reason = userrep.check_if_ok()
    if not ok:
        denyied = "Something went wrong, please try again later."
        if reason in ["messagelimit", "ban"]:
            denyied = "You have exceeded the daily rate limit."
        await ctx.send(content=denyied, ephemeral=True)
        return False
    serverrep.modify_status()
    userrep.modify_status()
    return True


def ai_rate_check():
    # the check
    async def check_2(ctx):
        return await check_ai_rate(ctx)

    return commands.check(check_2)


async def oai_check_actual(ctx):
    if not ctx.guild:
        await ctx.send(SERVER_ONLY_ERROR, ephemeral=True)
        return False
    if await ctx.bot.gptapi.check_oai(ctx):
        await ctx.send(INVALID_SERVER_ERROR, ephemeral=True)
        return False
    return True


def oai_check():
    # the check
    async def oai_check_2(ctx):
        return await oai_check_actual(ctx)

    return commands.check(oai_check_2)


async def read_article_async(jsctx: JSContext, url, clearout=True):
    myfile = await assetloader.JavascriptLookup.get_full_pathas(
        "readwebpage.js", "WEBJS", jsctx
    )
    gui.dprint(url)
    rsult = await myfile.read_webpage_plain(url, timeout=45)

    output = await rsult.get_a("mark")
    header = await rsult.get_a("orig")
    serial = await header.get_dict_a()

    simplified_text = output.strip()
    simplified_text = simplified_text.replace("*   ", "* ")
    if clearout:
        simplified_text = re.sub(r"(\n){4,}", "\n\n\n", simplified_text)
        simplified_text = re.sub(r"\n\n", "\n", simplified_text)

        simplified_text = re.sub(r" {3,}", "  ", simplified_text)
        simplified_text = simplified_text.replace("\t", "")
        simplified_text = re.sub(r"\n+(\s*\n)*", "\n", simplified_text)

    return simplified_text, serial


async def read_article(jsctx, url):
    now = discord.utils.utcnow()
    result = await read_article_async(jsctx, url)
    gui.gprint("elapsed", discord.utils.utcnow() - now)
    text, header = result[0], result[1]
    return text, header


def extract_masked_links(markdown_text):
    """just get all masked links."""
    pattern = r"\[([^\]]+)\]\(([^\)]+)\)"
    matches = re.findall(pattern, markdown_text)
    masked_links = []
    for match in matches:
        link_text, url = match
        masked_links.append((link_text, url))
    return masked_links


def generate_article_metatemplate(article_data, include_snppit=False):
    template_parts = []
    values = []
    if "title" in article_data:
        template_parts.append("Article Title: {}")
        values.append(article_data["title"])
    if "length" in article_data:
        template_parts.append("Length : {} characters")
        values.append(str(article_data.get("length", "UNKNOWN")))
    if "byline" in article_data:
        template_parts.append("byline: {}")
        values.append(article_data["byline"])
    if "siteName" in article_data:
        template_parts.append("siteName: {}")
        values.append(article_data["siteName"])
    if "publishedTime" in article_data:
        template_parts.append("publishedTime: {}")
        values.append(article_data["publishedTime"])

    if include_snppit and "excerpt" in article_data:
        template_parts.append("excerpt: {}")
        values.append(article_data["excerpt"])
    template = ";\n    ".join(template_parts)
    template = "Article Metadata: \n    " + template + ";\n    "

    return template.format(*values)


target_server = AssetLookup.get_asset("oai_server")

print("Defining Research Cog")


class ResearchCog(commands.Cog, TC_Cog_Mixin):
    """Collection of commands."""

    def __init__(self, bot: TCBot):
        self.helptext = "This cog is for AI powered websearch and summarization."
        self.bot: TCBot = bot
        self.lock = asyncio.Lock()

        self.translationprompt = """
        Given text from a non-English language, provide an accurate English translation, followed by contextual explanations for why and how the text's components conveys that meaning. Organize the explanations in a list format, with each word/phrase/component followed by its corresponding definition and explanation.  Note any double meanings within these explanations.
        """
        self.simpletranslationprompt = """
        Given text from a non-English language, provide an accurate English translation.  If any part of the non-English text can be translated in more than one possible way, provide all possible translations for that part in parenthesis.
        """
        self.init_context_menus()

    @super_context_menu(name="Translate")
    async def translate(
        self, interaction: discord.Interaction, message: discord.Message
    ) -> None:
        context = await self.bot.get_context(interaction)
        guild = interaction.guild
        user = interaction.user
        if not await oai_check_actual(context):
            return
        if not await check_ai_rate(context):
            return

        chat = gptmod.ChatCreation(
            messages=[{"role": "system", "content": self.translationprompt}]
        )

        totranslate = message.content
        if message.embeds:
            for m in message.embeds:
                result = ra.tools.extract_embed_text(m)
                totranslate += f"\n {result}"
        chat.add_message(role="user", content=totranslate)

        # Call API
        bot = self.bot

        targetmessage = await context.send(
            content=f" <a:SquareLoading:1143238358303264798> Translating... ```{totranslate[:1800]}```"
        )

        res = await bot.gptapi.callapi(chat)
        # await ctx.send(res)
        gui.dprint(res)
        result = res.choices[0].message.content
        embeds = []
        pages = commands.Paginator(prefix="", suffix="", max_size=3890)
        for l in result.split("\n"):
            pages.add_line(l)
        for e, p in enumerate(pages.pages):
            embed = discord.Embed(
                title="Translation" if e == 0 else f"Translation {e + 1}",
                description=p,
            )
            embeds.append(embed)

        await targetmessage.edit(content=message.content, embed=embeds[0])
        for e in embeds[1:]:
            await context.send(embed=e)

    @AILibFunction(
        name="google_search",
        description="Get a list of results from a google search query.",
        enabled=False,
        force_words=["google", "search"],
        required=["comment"],
    )
    @LibParam(
        comment="An interesting, amusing remark.",
        query="The query to search google with.",
        limit="Maximum number of results",
    )
    @commands.command(
        name="google_search",
        description="Get a list of results from a google search query.",
        extras={},
    )
    async def google_search(
        self,
        ctx: commands.Context,
        query: str,
        comment: str = "Search results:",
        limit: int = 7,
    ):
        "Search google for a query."
        bot = ctx.bot
        if "google" not in bot.keys or "cse" not in bot.keys:
            return "insufficient keys!"

        results = ra.tools.google_search(ctx.bot, query, limit)
        allstr = ""
        emb = discord.Embed(title="Search results", description=comment)
        readable_links = []
        messages = await ctx.send("Search completed, indexing.")

        def indent_string(inputString, spaces=2):
            indentation = " " * spaces
            indentedString = "\n".join(
                [indentation + line for line in inputString.split("\n")]
            )
            return indentedString

        outputthis = f"### Search results for {query} \n\n"
        for r in results["items"]:
            desc = r.get("snippet", "NA")
            allstr += r["link"] + "\n"
            emb.add_field(
                name=f"{r['title'][:200]}",
                value=f"{r['link']}\n{desc}"[:1000],
                inline=False,
            )
            outputthis += f"+ **Title: {r['title']}**\n **Link:**{r['link']}\n **Snippit:**\n{indent_string(desc, 1)}"
        returnme = await ctx.send(content=comment, embed=emb)
        return outputthis

    @commands.hybrid_command(
        name="translate_simple", description="Translate a block of text."
    )
    @oai_check()
    @ai_rate_check()
    async def translatesimple(self, context, text: str):
        chat = gptmod.ChatCreation(
            messages=[{"role": "system", "content": self.simpletranslationprompt}]
        )
        chat.add_message(role="user", content=text)

        # Call API
        bot = self.bot

        targetmessage = await context.send(content="Translating...")

        res = await bot.gptapi.callapi(chat)
        # await ctx.send(res)
        gui.dprint(res)
        result = res["choices"][0]["message"]["content"]
        embeds = []
        pages = commands.Paginator(prefix="", suffix="", max_size=2000)
        for l in result.split("\n"):
            pages.add_line(l)
        for e, p in enumerate(pages.pages):
            embed = discord.Embed(
                title="Translation" if e == 0 else f"Translation {e + 1}",
                description=p,
            )
            embeds.append(embed)

        await targetmessage.edit(content=text, embed=embeds[0])
        for e in embeds[1:]:
            await context.send(embed=e)

    @AILibFunction(
        name="read_url",
        description="If given a URL, use this function to read it.",
        enabled=True,
        required=["url", "comment"],
    )
    @LibParam(
        comment="An interesting, amusing remark.",
        url="The url that will be read.",
    )
    @commands.command(
        name="read_url",
        description="read a url",
        extras={},
    )
    @oai_check()
    @ai_rate_check()
    async def read_url(
        self,
        ctx: commands.Context,
        url: str,
        comment: str,
    ):
        "recall docs for question."

        mes = await ctx.channel.send(
            "<a:LoadingBlue:1206301904863502337> Reading Article <a:LoadingBlue:1206301904863502337>"
        )
        try:
            article, header = await read_article(ctx.bot.jsenv, url)
        except Exception:
            me = await ctx.send("I couldn't read the url.  Sorry.")
            return me
        await mes.delete()

        prompt = generate_article_metatemplate(header, include_snppit=False)
        sources = []
        mylinks = extract_masked_links(article)
        for link in mylinks:
            link_text, url4 = link
            link_text = link_text.replace("_", "")
            gui.dprint(link_text, url4)
            sources.append(f"[{link_text}]({url4})")

        await ctx.send(prompt, suppress_embeds=True)

        def local_length(st: str) -> int:
            return gptmod.util.num_tokens_from_messages(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": st},
                ],
                "gpt-4o-mini",
            )

        fil = prioritized_string_split(
            article, ra.tools.splitorder, 2000, length=local_length
        )
        filelength: int = len(fil)
        if len(fil) > 1:
            prompt = generate_article_metatemplate(header, include_snppit=True)
        output = f"{prompt}\n\n #Page 1/{filelength}\n{fil[0]}"
        splitorder = ["%s\n", "%s.", "%s,", "%s "]
        fil2 = prioritized_string_split(output, splitorder, 4072)
        title = header.get("title", "notitle")
        for p in fil2:
            emb = discord.Embed(title=title, description=p)
            await ctx.send(embed=emb)

        return output

    @commands.command(
        name="reader",
        description="read a website in reader mode, converted to markdown",
        extras={},
    )
    async def webreader(
        self,
        ctx: commands.Context,
        url: str,
        filter_links: bool = False,
        escape_markdown: bool = False,
    ):
        """
        Asynchronously load a web page's text, optionally filtering out links and/or escaping markdown special characters.

        Parameters
        ----------
        url : str
            The URL of the web page to be read.
        filter_links : bool, optional
            Whether to filter out markdown style links from the text, by default False.
        escape_markdown : bool, optional
            Whether to escape markdown special characters in the text, by default False.
        """
        async with self.lock:
            message = ctx.message
            guild = message.guild
            user = message.author
            mes = await ctx.channel.send(
                "<a:LoadingBlue:1206301904863502337> Reading Article <a:LoadingBlue:1206301904863502337>"
            )
            try:
                async with ctx.channel.typing():
                    article, header = await read_article_async(ctx.bot.jsenv, url)
            except Exception as e:
                await mes.edit(
                    content="I couldn't read the link, sorry.  It might be too large."
                )
                raise e
            await mes.delete()

            def filter_inline_links(markdown_string):
                return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", markdown_string)

            filtered_markdown = article
            if filter_links:
                filtered_markdown = filter_inline_links(article)
                gui.dprint(filtered_markdown)

            splitorder = [("\n## %s", 1000), ("\n### %s", 4000), ("%s\n", 4000)]
            fil = prioritized_string_split(filtered_markdown, splitorder)

            mytitle = header.get("title", "notitle")
            await ctx.send(f"# {mytitle}")
            length = len(fil)
            embeds = []
            for e, d in enumerate(fil):
                use = d
                if escape_markdown:
                    use = discord.utils.escape_markdown(d)
                emb = discord.Embed(title=f"{mytitle}: {e}/{length}", description=use)
                embeds.append(emb)
            if len(embeds) > 5:
                message = await pages_of_embeds(ctx, display=embeds)
            else:
                for e in embeds:
                    await ctx.send(embed=e)

    @commands.command(
        name="summarize", description="make a summary of a url.", extras={}
    )
    @oai_check()
    @ai_rate_check()
    async def summarize(
        self, ctx: commands.Context, url: str, over: bool = False, additional: str = ""
    ):
        """Download the reader mode view of a passed in URL, and summarize it."""
        async with self.lock:
            message = ctx.message
            guild = message.guild
            user = message.author

            mes = await ctx.channel.send(
                "<a:LoadingBlue:1206301904863502337> Reading Article <a:LoadingBlue:1206301904863502337>"
            )
            try:
                article, header = await read_article(ctx.bot.jsenv, url)
            except Exception as e:
                await mes.edit(
                    content="I couldn't read the link, sorry.  It might be too large."
                )
                raise e
            await mes.delete()

            prompt = generate_article_metatemplate(header)
            sources = []
            mylinks = extract_masked_links(article)
            for link in mylinks:
                link_text, url4 = link
                link_text = link_text.replace("_", "")
                gui.dprint(link_text, url4)
                sources.append(f"[{link_text}]({url4})")
            prompt = prompt + additional
            await ctx.send(prompt, suppress_embeds=True)
            try:
                all = ""
                async with ctx.channel.typing():
                    async for result in ra.tools.summarize(prompt, article, mylinks):
                        splitorder = ["%s\n", "%s.", "%s,", "%s "]
                        fil = prioritized_string_split(result, splitorder, 4072)
                        title = header.get("title", "notitle")
                        for p in fil:
                            embed = discord.Embed(title=title, description=p)
                            await ctx.send(embed=embed)
                        all += result

            except Exception as e:
                await ctx.bot.send_error(e)
                return await ctx.send(e)


async def setup(bot):
    await bot.add_cog(ResearchCog(bot))
