import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple

import discord
import gptfunctionutil.functionlib as gptum
from discord import app_commands
from discord.ext import commands
from gptfunctionutil import (
    AILibFunction,
    LibParam,
)
from javascriptasync import JSContext

import cogs.ResearchAgent as ra
import gptmod
from gptmod.lancetools import LanceTools
import gui
import assetloader
from assetloader import AssetLookup
from bot import StatusEditMessage, TC_Cog_Mixin, TCBot, super_context_menu
from database.database_ai import AuditProfile
from utility import prioritized_string_split
from utility.embed_paginator import pages_of_embeds
import importlib

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
    gui.dprint(rsult)

    output = await rsult.get_a("mark")
    header = await rsult.get_a("orig")
    gui.gprint(output)
    gui.gprint(header)
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


class Followups(gptum.GPTFunctionLibrary):
    @gptum.AILibFunction(
        name="followupquestions",
        description="Create a list of follow up questions to expand on a query.  Each follup question should contain a portion of the prior query!",
    )
    @gptum.LibParamSpec(
        name="followup",
        description="A list of followup questions.",
        minItems=3,
        maxItems=10,
    )
    async def make_followups(self, followup: List[str]):
        # Wait for a set period of time.
        gui.dprint("foll:", followup)

        return followup

    @gptum.AILibFunction(
        name="google_search",
        description="Solve a question using a google search.  Form the query based on the question, and then use the page text from the search results to create an answer.",
        required=["comment", "question", "query"],
    )
    @gptum.LibParam(
        comment="An interesting, amusing remark.",
        query="The query to search google with.  Must be related to the question.",
        question="The question that is to be solved with this search.  Must be a complete sentence.",
        result_limit="Number of search results to retrieve.  Minimum of 3,  Maximum of 16.",
    )
    async def google_search(
        self,
        question: str,
        query: str,
        comment: str = "Search results:",
        result_limit: int = 7,
    ):
        # Wait for a set period of time.
        gui.dprint("foll:", query, question)

        return query, question, comment


target_server = AssetLookup.get_asset("oai_server")


class ResearchCogStore(commands.Cog, TC_Cog_Mixin):
    """Collection of commands."""

    def __init__(self, bot: TCBot):
        self.helptext = "This cog is for AI powered websearch and summarization."
        self.bot: TCBot = bot
        self.lock = asyncio.Lock()

        self.manual_enable = True
        self.private = True

        self.translationprompt = """
        Given text from a non-English language, provide an accurate English translation, followed by contextual explanations for why and how the text's components conveys that meaning. Organize the explanations in a list format, with each word/phrase/component followed by its corresponding definition and explanation.  Note any double meanings within these explanations.
        """
        self.simpletranslationprompt = """
        Given text from a non-English language, provide an accurate English translation.  If any part of the non-English text can be translated in more than one possible way, provide all possible translations for that part in parenthesis.
        """
        self.init_context_menus()

    async def load_links(
        self,
        ctx: commands.Context,
        all_links: List[str],
        lancedbc: Any = None,
        statmess: StatusEditMessage = None,
        embed: discord.Embed = None,
        override: bool = False,
    ):
        """
        Asynchronously loads links, checks for cached documents, and processes the split content.

        Args:
            ctx (commands.Context): The context of the command.
            all_links (List[str]): List of links to be processed.
            lancec (Any, optional): Lance client for link processing. Defaults to None.
            statmess (StatusEditMessage, optional): Status message to edit during processing. Defaults to None.
            override (bool, optional): If True, override cache and process all links. Defaults to False.

        Returns:
            Tuple[int, str]: A tuple containing the count of successfully processed links and a formatted status string.
        """
        gui.gprint("Starting source loader.")
        loader = ra.SourceLinkLoader(
            lance_connection=lancedbc, statusmessage=statmess, embed=embed
        )
        return await loader.load_links(ctx, all_links, override)

    async def web_search(
        self,
        ctx: commands.Context,
        query: str,
        result_limit: int = 7,
    ) -> Tuple[List[str], List[Dict[str, str]]]:
        bot = ctx.bot
        # Pre check.
        if not ctx.guild:
            await ctx.send("needs to be guild")
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(INVALID_SERVER_ERROR)
            return "INVALID CONTEXT"
        if "google" not in bot.keys or "cse" not in bot.keys:
            await ctx.send("google search keys not set up.")
            return "insufficient keys!"

        target_message = await ctx.channel.send(
            f"<a:SquareLoading:1143238358303264798> Searching google for {query} ..."
        )

        # SEARCH FOR AND LOAD.
        res = []
        async with ctx.channel.typing():
            results = ra.tools.google_search(ctx.bot, query, result_limit)
            if "items" not in results:
                return [], [
                    {
                        "title": "No results",
                        "link": "NA",
                        "desc": "no results for that query.",
                    }
                ]
            all_links = [r["link"] for r in results["items"]]
            hascount = 0
            length = len(results)
            lines = "\n".join([f"- {r['link']}" for r in results["items"]])
            emb = discord.Embed(
                title=f"query: {query}", description=f"Links: \n{lines}"
            )
            for r in results["items"]:
                desc = r.get("snippet", "NA")
                res.append({"title": r["title"], "link": r["link"], "desc": desc})
        await target_message.delete()
        return all_links, res

    @AILibFunction(
        name="google_detective",
        description="Solve a question using a google search.  Form the query based on the question, and then use the page text from the search results to create an answer.",
        enabled=False,
        force_words=["research"],
        required=["comment"],
    )
    @LibParam(
        comment="An interesting, amusing remark.",
        query="The query to search google with.  Must be related to the question.",
        question="the question that is to be solved with this search.  Must be a complete sentence.",
        site_title_restriction="Optional restrictions for sources.  Only sources with this substring in the title will be considered when writing the answer.  Include only if user explicitly asks.",
        result_limit="Number of search results to retrieve.  Minimum of 3,  Maximum of 16.",
    )
    @commands.command(
        name="google_detective",
        description="Get a list of results from a google search query.",
        extras={},
    )
    @oai_check()
    @ai_rate_check()
    async def google_detective(
        self,
        ctx: commands.Context,
        question: str,
        query: str,
        comment: str = "Search results:",
        site_title_restriction: str = "None",
        result_limit: int = 7,
    ):
        "Search google for a query."

        lancedbc = LanceTools.get_lance_client()
        # Preform web search
        all_links, res = await self.web_search(ctx, query, result_limit=result_limit)
        embed = discord.Embed(
            title=f"Web Search Results for: {query} ",
        )
        for v in res:
            embed.add_field(name=v["title"], value=v["desc"], inline=True)
        target_message = await ctx.send(embed=embed)

        statmess = StatusEditMessage(target_message, ctx)

        hascount, lines = await self.load_links(ctx, all_links, lancedbc, statmess)
        await statmess.delete()
        # DISPLAY RESULTS OF SEARCH.
        embed = discord.Embed(
            title=f"Web Search Results for: {query} ",
            description=f"Links\n{lines}",
        )
        for v in res:
            embed.add_field(name=v["title"], value=v["desc"], inline=True)
        embed.add_field(name="Question", value=question, inline=False)
        if site_title_restriction != "None":
            embed.add_field(name="restrict", value=site_title_restriction, inline=False)
        embed.set_footer(text=comment)

        await ctx.send(embed=embed)
        #
        answer, links, ms = await self.research(
            ctx,
            question,
            k=10,
            site_title_restriction=site_title_restriction,
            send_message=True,
        )

        return ra.tools.mask_links(answer, links)

    @AILibFunction(
        name="recall",
        description="Recall up to 12 sources that could be related to the user's question.",
        enabled=False,
        force_words=["recall"],
        required=["comment", "question"],
    )
    @LibParam(
        comment="An interesting, amusing remark.",
        question="the question that is to be solved with this search.  Must be a complete sentence.",
        site_title_restriction="Optional restrictions for sources.  Only sources with this substring in the title will be considered when writing the answer.  Include only if user explicitly asks.",
        result_limit="Number of search results to retrieve.  Minimum of 3,  Maximum of 16.",
    )
    @commands.command(
        name="recall_docs",
        description="Get a list of results from a google search query.",
        extras={},
    )
    @oai_check()
    @ai_rate_check()
    async def recall_docs(
        self,
        ctx: commands.Context,
        question: str,
        comment: str = "Search results:",
        site_title_restriction: str = "None",
        result_limit: int = 7,
    ):
        "recall docs for question."
        await ctx.send("RECALLING")
        m = await ctx.send("O")
        statmess = StatusEditMessage(m, ctx)
        out = await ra.actions.get_sources(
            question,
            result_limit,
            site_title_restriction,
            False,
            statmess=statmess,
            link_restrict=[],
        )

        return out

    @commands.command(name="loadurl", description="loadurl test.", extras={})
    async def loader_test(self, ctx: commands.Context, link: str):
        async with ctx.channel.typing():
            splits, e, dat = await ra.tools.read_and_split_link(ctx.bot, link)
        if isinstance(splits, Exception):
            views = await ctx.send(
                f"{type(splits).__name__},{str(splits)}",
            )
            return
        # vi=FollowupActionView(user=ctx.author)
        views = await ctx.send(
            f"[Link ]({link}) has {len(splits)} splits.",
            suppress_embeds=True,
            # view=vi
        )
        for i in splits[0:3]:
            await ctx.send(f"```{str(i.page_content)}```"[:1980], suppress_embeds=True)

    @commands.is_owner()
    @commands.command(name="loadmany")
    @oai_check()
    @ai_rate_check()
    async def loadmany(self, ctx: commands.Context, over: bool = False, *, links: str):
        """'Load many urls into the collection, with each link separated by a newline.

        over:bool-> whether or not to override links.  default false.
        links:str
        """
        bot = ctx.bot

        lancedbc = LanceTools.get_lance_client()
        all_links = [link for link in links.split("\n")]
        target_message = await ctx.send(
            f"<a:SquareLoading:1143238358303264798> Retrieving {len(all_links)} ..."
        )

        statmess = StatusEditMessage(target_message, ctx)
        # async for dat, e, typev in ra.tools.read_and_split_links(bot,all_links):
        #      views = await ctx.send(
        #         f"{len(dat)} splits.",
        #         suppress_embeds=True,
        #         # view=vi
        #     )
        # return
        hascount, lines = await self.load_links(
            ctx, all_links, lancedbc, statmess, override=over
        )
        embed = discord.Embed(
            title="Collection load results",
            description=f"{hascount}/{len(all_links)}\nout=\n{lines}",
        )
        embed.set_footer(text="Operation complete.")
        await statmess.delete()
        await ctx.send(embed=embed)

    @commands.is_owner()
    @commands.command(name="removeurl")
    @oai_check()
    async def remove_url(self, ctx: commands.Context, link: str):
        """'replace a url in documents.
        link:str
        """
        bot = ctx.bot
        if not ctx.guild:
            await ctx.send(SERVER_ONLY_ERROR)
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(INVALID_SERVER_ERROR)
            return "INVALID CONTEXT"

        lancedbc = LanceTools.get_lance_client()
        has, getres = ra.storage_tools.has_url(link, client=lancedbc)
        if has:
            ra.storage_tools.remove_url(link, client=lancedbc)

            await ctx.send("removal complete")
        else:
            ra.storage_tools.remove_url(link, client=lancedbc)
            await ctx.send("Link not in database")

    @commands.is_owner()
    @commands.hybrid_command(
        name="loadurlover",
        description="replace or load a url into my document_store documents.",
        extras={},
    )
    @oai_check()
    @app_commands.describe(link="URL to add to my database.")
    async def loadover(self, ctx: commands.Context, link: str):
        """'replace a url in documents.
        link:str
        """
        bot = ctx.bot
        if not ctx.guild:
            await ctx.send(SERVER_ONLY_ERROR)
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(INVALID_SERVER_ERROR)
            return "INVALID CONTEXT"

        lancedbc = LanceTools.get_lance_client()

        target_message = await ctx.send(
            f"<a:LoadingBlue:1206301904863502337> Retrieving {link} ..."
        )

        statmess = StatusEditMessage(target_message, ctx)
        async with ctx.channel.typing():
            hc, lines = await self.load_links(
                ctx, [link], lancedbc, statmess=None, override=True
            )
            embed = discord.Embed(
                title="Website Load Results",
                description=f"{1}/{1}\nout=\n{lines}",
            )
            embed.set_footer(text="Operation complete.")
            await statmess.editw(min_seconds=0, content="Overwrite ok.", embed=embed)

    @commands.hybrid_command(
        name="researchcached", description="Research a topic.", extras={}
    )
    @oai_check()
    @ai_rate_check()
    @app_commands.guilds(int(target_server[1]))
    @app_commands.describe(question="question to be asked.")
    @app_commands.describe(k="min number of sources to grab.")
    @app_commands.describe(use_mmr="Use the max_marginal_relevance_search")
    @app_commands.describe(
        site_title_restriction="Restrain query to websites with this in the title."
    )
    async def researchcached(
        self,
        ctx: commands.Context,
        question: str,
        k: int = 5,
        site_title_restriction: str = "None",
        use_mmr: bool = False,
    ):
        bot = ctx.bot
        if not ctx.guild:
            await ctx.send("needs to be guild")
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(INVALID_SERVER_ERROR)
            return "INVALID CONTEXT"
        answer, links, message = await self.research(
            ctx, question, k, site_title_restriction, use_mmr
        )
        return answer, message

    async def research(
        self,
        ctx: commands.Context,
        question: str,
        k: int = 5,
        site_title_restriction: str = "None",
        use_mmr: bool = False,
        send_message: bool = True,
    ) -> Tuple[
        str,
        Optional[str],
        Optional[discord.Message],
    ]:
        """Search the lance db for relevant documents pertaining to the
        question, and return a formatted result.

        Args:
            ctx (commands.Context): The context in which the command is being invoked.
            question (str): The research question.
            k (int, optional): The number of query results to consider. Defaults to 5.
            site_title_restriction (str, optional): Restricts search to sites with this title.
              Defaults to "None".
            use_mmr (bool, optional): Whether to use Maximal Marginal Relevance for deduplication.
            Defaults to False.
            send_message (bool, optional): Whether to send the research result as a message
                in the channel.
            Defaults to True.

        Returns:
            Tuple[str, Optional[discord.Message]]:
                A tuple containing the research answer and the sent message object (if any).
        """

        res = await ctx.send("<a:LoadingBlue:1206301904863502337> querying db...")
        statmess = StatusEditMessage(res, ctx)

        embed = discord.Embed(title=f"Query: {question} ")

        embed.add_field(name="Question", value=question, inline=False)
        if site_title_restriction != "None":
            embed.add_field(name="restrict", value=site_title_restriction, inline=False)
        await statmess.editw(
            min_seconds=0,
            embed=embed,
        )
        async with ctx.channel.typing():
            # Search For Sources
            answer, allsources, docs2 = await ra.actions.research_op(
                question, k, site_title_restriction, use_mmr, statmess
            )
            viewme = Followup(bot=ctx.bot, answer=answer, page_content=docs2)
            messageresp = None
            if send_message:
                pages = prioritized_string_split(answer, ["%s\n"], 2000)
                pl = len(pages)
                for e, pa in enumerate(pages):
                    if e == pl - 1:
                        ms = await ctx.channel.send(pa, view=viewme)
                    else:
                        ms = await ctx.channel.send(pa)
                    if messageresp is None:
                        messageresp = ms
            # await ctx.channel.send("Click button for sources.", view=viewme)
            return answer, allsources, messageresp

    @commands.hybrid_command(
        name="researchpoint",
        description="Extract relevant information from the given sources.",
        extras={},
    )
    @oai_check()
    @ai_rate_check()
    @app_commands.guilds(int(target_server[1]))
    @app_commands.describe(question="question to be asked.")
    @app_commands.describe(k="min number of sources to grab.")
    @app_commands.describe(use_mmr="Use the max_marginal_relevance_search")
    @app_commands.describe(
        site_title_restriction="Restrain query to websites with this in the title."
    )
    async def research_bullet(
        self,
        ctx: commands.Context,
        question: str,
        k: int = 5,
        site_title_restriction: str = "None",
        use_mmr: bool = False,
    ):
        """
        question:str-Question you want to ask
        site_title_restriction-Restrict to all with this in the title.
        """
        bot = ctx.bot
        if not ctx.guild:
            await ctx.send("needs to be guild")
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(INVALID_SERVER_ERROR)
            return "INVALID CONTEXT"

        lanceclient = LanceTools.get_lance_client()
        res = await ctx.send("ok")
        statmess = StatusEditMessage(res, ctx)
        embed = discord.Embed(title=f"Search Query: {question} ", description="ok")
        embed.add_field(name="Question", value=question, inline=False)
        if site_title_restriction != "None":
            embed.add_field(name="restrict", value=site_title_restriction, inline=False)
        await statmess.editw(
            min_seconds=0,
            content="<a:LoadingBlue:1206301904863502337> querying db...",
            embed=embed,
        )
        async with ctx.channel.typing():
            data = await ra.storage_tools.search_sim(
                question,
                client=lanceclient,
                titleres=site_title_restriction,
                k=k,
                mmr=use_mmr,
            )

            if len(data) <= 0:
                return "NO RELEVANT DATA."
            docs2 = sorted(data, key=lambda x: x[1], reverse=False)
            # Get string containing most relevant source urls:
            url_desc, all_sources = ra.tools.get_doc_sources(docs2)
            embed.description = f"{url_desc}"
            embed.add_field(
                name="Cache_Query",
                value=f"About {len(docs2)} entries where found.  Max score is {docs2[0][1]}",
            )
            # docs2 = sorted(data, key=lambda x: x[1],reverse=True)
            await statmess.editw(min_seconds=0, content="", embed=embed)
            answer = []
            async for doctup in ra.tools.get_points(question, docs2):
                doc, score, content, tokens = doctup
                meta = doc.metadata
                emb = discord.Embed(title=meta.get("title", "?"), description=content)
                emb.add_field(name="source", value=meta["source"], inline=False)
                emb.add_field(name="score", value=f"{score * 100.0:.4f}")
                emb.add_field(name="split value", value=f"{meta.get('split', '?')}")
                emb.add_field(name="source_tokens", value=f"{tokens}")
                answer.append(doctup)
                await ctx.send(embed=emb)

            return answer

    @commands.command(name="get_source", description="get sources.", extras={})
    @oai_check()
    async def source_get(self, ctx: commands.Context, question: str):
        lancedbc = LanceTools.get_lance_client()
        data = await ra.storage_tools.search_sim(
            question, client=lancedbc, titleres="None"
        )
        len(data)
        if len(data) <= 0:
            await ctx.send("NO RELEVANT DATA.")
        docs2 = sorted(data, key=lambda x: x[1], reverse=False)
        embed = discord.Embed(title="sauces")
        for doc, score in docs2[:10]:
            # gui.dprint(doc)
            # 'metadata',{'title':'UNKNOWN','source':'unknown'})
            meta = doc.metadata
            content = doc.page_content  # ('page_content','Data l
            output = f"""**Name:** {meta["title"][:100]}
            **Link:** {meta["source"]}
            **Text:** {content[:512]}..."""
            # await ctx.send(output,suppress_embeds=True)
            embed.add_field(name=f"s: score:{score}", value=output[:1024], inline=False)
        await ctx.send(embed=embed)
        embed = discord.Embed(title="sauces")
        field_count = 0
        embeds = []
        for doc, score in docs2[:10]:
            if field_count == 3:
                # Send the embed here or add it to a list of embeds
                # Reset the field count and create a new embed
                field_count = 0
                embeds.append(embed)
                embed = discord.Embed(title="sauces")

            meta = doc.metadata
            content = doc.page_content
            output = f"""**ID**: ?
        **Name:** {meta["title"]}
        **Link:** {meta["source"]}
        **Text:** {content}"""
            embed.add_field(name=f"s: score:{score}", value=output[:1020], inline=False)
            field_count += 1
        embeds.append(embed)
        pcc, buttons = await pages_of_embeds_2("ANY", embeds)

        await ctx.channel.send(embed=pcc.make_embed(), view=buttons)
        # viewme=Followup(bot=self.bot,page_content=docs2)
        # await ctx.channel.send(f'{len(data)} sources found',view=viewme)

    @AILibFunction(
        name="code_gen",
        description="Output a block of formatted code in accordance with the user's instructions.",
        required=["comment"],
        enabled=False,
        force_words=["generate code"],
    )
    @LibParam(
        comment="An interesting, amusing remark.",
        code="Formatted computer code in any language to be given to the user.",
    )
    @commands.command(name="code_generate", description="generate some code")
    async def codegen(
        self, ctx: commands.Context, code: str, comment: str = "Search results:"
    ):
        # This is an example of a decorated discord.py command.
        bot = ctx.bot
        emb = discord.Embed(title=comment, description=f"```py\n{code}\n```")
        returnme = await ctx.send(content=comment + f"{code[:1024]}", embed=emb)
        return returnme

    @commands.command(
        name="summarize_db", description="make a summary of a url.", extras={}
    )
    @oai_check()
    @ai_rate_check()
    async def summarize_db(
        self, ctx: commands.Context, url: str, over: bool = False, stopat: str = None
    ):
        """Generate a summary of an already loaded source."""
        await ctx.send("Command is unused")

    @commands.hybrid_command(
        name="research_recursive",
        description="Research a topic with multiple queries.",
        extras={},
    )
    @oai_check()
    @ai_rate_check()
    @app_commands.guilds(int(target_server[1]))
    @app_commands.describe(question="question to be asked.")
    @app_commands.describe(k="min number of sources to grab.")
    @app_commands.describe(use_mmr="Use the max_marginal_relevance_search")
    @app_commands.describe(depth="Maximum query depth.")
    @app_commands.describe(followup="number of followup questions after each search.")
    @app_commands.describe(
        site_title_restriction="Restrain query to websites with this in the title."
    )
    @app_commands.describe(
        search_web="set to 1-10 if additional web searches will be needed."
    )
    async def research_recursive(
        self,
        ctx: commands.Context,
        question: str,
        k: int = 5,
        site_title_restriction: str = "None",
        use_mmr: bool = False,
        depth: commands.Range[int, 1, 4] = 1,
        followup: commands.Range[int, 1, 5] = 2,
        search_web: commands.Range[int, 0, 10] = 0,
    ):
        """
        Begin to recursively research the user's query, deriving an answer
        using the stored documents in the chroma database.

        Args:
            ctx (commands.Context): commands:context
            question (str): Question to be asked
            k (int, optional): Sources per call to research. Defaults to 5.
            site_title_restriction (str, optional): _description_. Defaults to "None".
            use_mmr (bool, optional): Whether or not to use Max Marginal Search. Defaults to False.
            depth (commands.Range[int, 1, 4], optional): The max depth of the recursive query. Defaults to 1.
            followup (commands.Range[int, 1, 5], optional): The number of followup questions to ask per run. Defaults to 2.
            search_web (commands.Range[int, 0, 10], optional): Number of google search results to add per run. Defaults to 0.

        """
        if not ctx.guild:
            await ctx.send("needs to be guild")
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(INVALID_SERVER_ERROR)
            return "INVALID CONTEXT"

        research_context = ra.ResearchContext(
            self,
            ctx,
            k,
            site_title_restriction,
            use_mmr,
            depth,
            followup,
            search_web,
        )

        if not await research_context.setup():
            return
        research_context.add_to_stack(question, "", 0, research_context.res)
        while research_context.stack:
            current = research_context.stack.pop(0)
            await research_context.single_iteration(current)

        await research_context.send_file_results()
        await research_context.statmess.editw(
            min_seconds=0,
            content=f"about {len(research_context.alllines)} links where gathered.",
        )

    @commands.hybrid_command(
        name="research_manual",
        description="Manually research a topic.",
        extras={},
    )
    @oai_check()
    @ai_rate_check()
    @app_commands.guilds(int(target_server[1]))
    @app_commands.describe(question="question to be asked.")
    @app_commands.describe(k="min number of sources to grab.")
    @app_commands.describe(use_mmr="Use the max_marginal_relevance_search")
    @app_commands.describe(depth="Maximum query depth.")
    @app_commands.describe(followup="number of followup questions after each search.")
    @app_commands.describe(
        site_title_restriction="Restrain query to websites with this in the title."
    )
    @app_commands.describe(
        search_web="set to 1-10 if additional web searches will be needed."
    )
    async def research_manual(
        self,
        ctx: commands.Context,
        question: str,
        k: int = 5,
        site_title_restriction: str = "None",
        use_mmr: bool = False,
        depth: commands.Range[int, 1, 4] = 1,
        followup: commands.Range[int, 1, 5] = 2,
        search_web: commands.Range[int, 0, 10] = 0,
    ):
        """
        Begin to recursively research the user's query, deriving an answer
        using the stored documents in the lancedb database.

        Args:
            ctx (commands.Context): commands:context
            question (str): Question to be asked
            k (int, optional): Sources per call to research. Defaults to 5.
            site_title_restriction (str, optional): _description_. Defaults to "None".
            use_mmr (bool, optional): Whether or not to use Max Marginal Search. Defaults to False.
            depth (commands.Range[int, 1, 4], optional): The max depth of the recursive query. Defaults to 1.
            followup (commands.Range[int, 1, 5], optional): The number of followup questions to ask per run. Defaults to 2.
            search_web (commands.Range[int, 0, 10], optional): Number of google search results to add per run. Defaults to 0.

        """
        if not ctx.guild:
            await ctx.send("needs to be guild")
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(INVALID_SERVER_ERROR)
            return "INVALID CONTEXT"

        research_context = ra.ResearchContext(
            self,
            ctx,
            k,
            site_title_restriction,
            use_mmr,
            depth,
            followup,
            search_web,
        )

        automode = True

        if not await research_context.setup():
            return
        research_context.add_to_stack(question, "", 0, research_context.res)

        while research_context.stack:
            current = research_context.stack.pop(0)

            qatup = ("No search.", current[0], "Let's find out.")
            # WEB SEARCH.
            if search_web:
                vie = ra.views.PreCheck(
                    user=ctx.author, timeout=75, rctx=research_context, current=current
                )
                if automode:
                    await vie.gen_query()
                    await vie.search(None, edit=False)
                message = await ctx.send(
                    embed=vie.embed,
                    view=vie,
                )
                await vie.wait()
                await message.edit(view=None)
                if vie.links:
                    qatup = vie.qatup
                    await research_context.load_links(vie.qatup, vie.links, vie.details)
            quest, context, dep, parent = current
            answer, links, ms = await research_context.research(quest)
            emb, mess = await research_context.format_results(
                quest, qatup, answer, parent
            )
            newcontext, depth = await research_context.change_context(
                quest, answer, context, dep, mess
            )

            if depth < research_context.depth and len(research_context.stack) <= 0:
                cur = (quest, newcontext, depth, parent)
                vie = ra.views.FollowupActionView(
                    user=ctx.author, timeout=60 * 7, rctx=research_context, current=cur
                )
                message = await ctx.send(
                    embed=discord.Embed(
                        title="Add up to 5 followup questions, or have the AI make them."
                    ),
                    view=vie,
                )
                await vie.wait()
                await message.edit(view=None)
                if vie.value and vie.followup_questions:
                    followups = "\n".join(f"* {q}" for q in vie.followup_questions)
                    await research_context.add_followups_to_stack(
                        vie.followup_questions, followups, newcontext, depth, mess
                    )
                    await research_context.load_links(vie.qatup, vie.links, vie.details)

            research_context.add_output_dict(quest, answer, links, dep, followups)

        await research_context.send_file_results()
        await research_context.statmess.editw(
            min_seconds=0,
            content=f"about {len(research_context.alllines)} links where gathered.",
        )


async def setup(bot):
    module_name = "cogs.ResearchAgent"
    try:
        importlib.reload(ra)
        gui.gprint(f"{module_name} reloaded successfully.")
    except ImportError:
        gui.gprint(f"Failed to reload {module_name}.")
    await bot.add_cog(ResearchCogStore(bot))
