from typing import Any, List
import discord
import asyncio
from assets import AssetLookup
import re

# import datetime


from discord.ext import commands

from discord import app_commands
from bot import TC_Cog_Mixin, StatusEditMessage, super_context_menu, TCBot

from .ResearchAgent import SourceLinkLoader
import gptmod
from gptfunctionutil import *
import gptmod.error
from database.database_ai import AuditProfile

from javascriptasync import JSContext
import assets
import gui

from .ResearchAgent.chromatools import ChromaTools
from .ResearchAgent.views import *

from utility import prioritized_string_split, select_emoji
from utility.embed_paginator import pages_of_embeds
import  cogs.ResearchAgent.tools as tools
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


async def read_article_async(jsctx:JSContext, url, clearout=True):
    myfile = await assets.JavascriptLookup.get_full_pathas(
        "readwebpage.js", "WEBJS", jsctx
    )
    print(url)
    rsult = await myfile.read_webpage_plain(url, timeout=45)
    # print(rsult)
    output = await rsult.get_a("mark")
    header = await rsult.get_a("orig")
    serial = await header.get_dict_a()
    # print(serial)
    simplified_text = output.strip()
    simplified_text = simplified_text.replace("*   ", "* ")
    if clearout:
        simplified_text = re.sub(r"(\n){4,}", "\n\n\n", simplified_text)
        simplified_text = re.sub(r"\n\n", "\n", simplified_text)

        simplified_text = re.sub(r" {3,}", "  ", simplified_text)
        simplified_text = simplified_text.replace("\t", "")
        simplified_text = re.sub(r"\n+(\s*\n)*", "\n", simplified_text)
    # print(simplified_text)
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


target_server = AssetLookup.get_asset("oai_server")


class ResearchCog(commands.Cog, TC_Cog_Mixin):
    """Collection of commands."""

    def __init__(self, bot: TCBot):
        self.helptext = "This cog is for AI powered websearch and summarization."
        self.bot: TCBot = bot
        self.lock = asyncio.Lock()
        self.prompt = """
        Summarize general news articles, forum posts, and wiki pages that have been converted into Markdown. Condense the content into 2-4 medium-length paragraphs with 3-7 sentences per paragraph. Preserve key information and maintain a descriptive tone, including the purpose of the article. The summary should be easily understood by a 10th grader. Exclude any concluding remarks from the summary.
        """
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
                result = tools.extract_embed_text(m)
                totranslate += f"\n {result}"
        chat.add_message(role="user", content=totranslate)

        # Call API
        bot = self.bot

        targetmessage = await context.send(
            content=f" <a:SquareLoading:1143238358303264798> Translating... ```{totranslate[:1800]}```"
        )

        res = await bot.gptapi.callapi(chat)
        # await ctx.send(res)
        print(res)
        result = res.choices[0].message.content
        embeds = []
        pages = commands.Paginator(prefix="", suffix="", max_size=3890)
        for l in result.split("\n"):
            pages.add_line(l)
        for e, p in enumerate(pages.pages):
            embed = discord.Embed(
                title=f"Translation" if e == 0 else f"Translation {e+1}", description=p
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

        results = tools.google_search(ctx.bot, query, limit)
        allstr = ""
        emb = discord.Embed(title="Search results", description=comment)
        readable_links = []
        messages = await ctx.send("Search completed, indexing.")
        for r in results:
            metatags = r["pagemap"]["metatags"][0]
            desc = metatags.get("og:description", "NO DESCRIPTION")
            allstr += r["link"] + "\n"
            emb.add_field(
                name=f"{r['title'][:200]}",
                value=f"{r['link']}\n{desc}"[:1200],
                inline=False,
            )
        returnme = await ctx.send(content=comment, embed=emb)
        return returnme
    
    async def load_links(
        self,
        ctx: commands.Context,
        all_links: List[str],
        chromac: Any = None,
        statmess: StatusEditMessage = None,
        override: bool = False,
    ):
        """
        Asynchronously loads links, checks for cached documents, and processes the split content.

        Args:
            ctx (commands.Context): The context of the command.
            all_links (List[str]): List of links to be processed.
            chromac (Any, optional): Chroma client for link processing. Defaults to None.
            statmess (StatusEditMessage, optional): Status message to edit during processing. Defaults to None.
            override (bool, optional): If True, override cache and process all links. Defaults to False.

        Returns:
            Tuple[int, str]: A tuple containing the count of successfully processed links and a formatted status string.
        """
        loader=SourceLinkLoader(chromac=chromac,statusmessage=statmess)
        return await loader.load_links(ctx,all_links,override)

        

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

        bot = ctx.bot
        #Pre check.
        if not ctx.guild:
            await ctx.send("needs to be guild")
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(INVALID_SERVER_ERROR)
            return "INVALID CONTEXT"
        if "google" not in bot.keys or "cse" not in bot.keys:
            await ctx.send("google search keys not set up.")
            return "insufficient keys!"

        chromac = ChromaTools.get_chroma_client()

        target_message = await ctx.channel.send(
            f"<a:SquareLoading:1143238358303264798> Searching google for {query} ..."
        )

        statmess = StatusEditMessage(target_message, ctx)
        current = ""
        # SEARCH FOR AND LOAD.
        async with ctx.channel.typing():
            results = tools.google_search(ctx.bot, query, result_limit)

            all_links = [r["link"] for r in results]
            hascount = 0
            length = len(results)
            lines = "\n".join([f"- {r['link']}" for r in results])

            await statmess.editw(
                min_seconds=0,
                content=f"<a:LetWalkR:1118191001731874856> Search complete: reading {0}/{length}. {hascount}/{len(all_links)}",
                embed=discord.Embed(
                    title=f"query: {query}", description=f"out=\n{lines}"
                ),
            )
            hascount, lines = await self.load_links(ctx, all_links, chromac, statmess)
        #DISPLAY RESULTS OF SEARCH.
        embed = discord.Embed(
            title=f"Web Search Results for: {query} ",
            description=f"{hascount}/{len(all_links)}\nout=\n{lines}",
        )
        embed.add_field(name="Question", value=question, inline=False)
        if site_title_restriction != "None":
            embed.add_field(name="restrict", value=site_title_restriction, inline=False)
        embed.set_footer(text=comment)
        
        await statmess.editw(min_seconds=0, content="querying db...", embed=embed)

        # 
        async with ctx.channel.typing():
            #Preform Simularity Search on Collection.
            data = await tools.search_sim(
                question, client=chromac, titleres=site_title_restriction
            )
            len(data)
            if len(data) <= 0:
                return "NO RELEVANT DATA."
            docs2 = sorted(data, key=lambda x: x[1], reverse=False)
            all_links=[doc.metadata.get("source",'???') for doc, e in docs2]
            links=set(doc.metadata.get("source",'???') for doc, e in docs2)
            def ie(all_links: List[str], value: str) -> List[int]:
                return [index for index, link in enumerate(all_links) if link == value]
            
            used="\n".join(f"{ie(all_links,l)}{l}" for l in links)
            fil = prioritized_string_split(used, ["%s\n"], 1020 )
            cont = '...' if len(fil)>2 else ""
            embed.add_field(name="Links_Used",value=f"{fil[0]}{cont}")
            embed.add_field(
                name="Cache_Query",
                value=f"About {len(docs2)} entries where found.  Max score is {docs2[0][1]}",
            )
            await statmess.editw(
                min_seconds=0, content="drawing conclusion...", embed=embed
            )
            answer = await tools.format_answer(question, docs2)
            page = commands.Paginator(prefix="", suffix=None)
            viewme = Followup(bot=self.bot, page_content=docs2)
            for p in answer.split("\n"):
                page.add_line(p)
            messageresp = None
            pages = [p for p in page.pages]
            pl = len(pages)
            for e, pa in enumerate(pages):
                if e == pl - 1:
                    ms = await ctx.channel.send(pa, view=viewme)
                else:
                    ms = await ctx.channel.send(pa)
                if messageresp is None:
                    messageresp = ms
            # await ctx.channel.send("complete", view=viewme)
            return messageresp

    @commands.command(name="loadurl", description="loadurl test.", extras={})
    async def loader_test(self, ctx: commands.Context, link: str):
        async with ctx.channel.typing():
            splits,dat = await tools.read_and_split_link(ctx.bot, link)
        await ctx.send(
            f"[Link ]({link}) has {len(splits)} splits.", suppress_embeds=True
        )
        for i in splits[0:3]:
            await ctx.send(f"```{str(i.page_content)}```"[:1980], suppress_embeds=True)

    @commands.is_owner()
    @commands.command(name="loadmany")
    @oai_check()
    @ai_rate_check()
    async def loadmany(self, ctx: commands.Context,  over: bool = False, *,links: str):
        """'Load many urls into the collection, with each link separated by a newline.
        
        over:bool-> whether or not to override links.  default false.
        links:str
        """
        bot = ctx.bot

        chromac = ChromaTools.get_chroma_client()
        all_links = [link for link in links.split("\n")]
        target_message = await ctx.send(
            f"<a:SquareLoading:1143238358303264798> Retrieving {len(all_links)} ..."
        )

        statmess = StatusEditMessage(target_message, ctx)

        hascount, lines = await self.load_links(
            ctx, all_links, chromac, statmess, override=over
        )
        embed = discord.Embed(
            title=f"Collection load results",
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

        chromac = ChromaTools.get_chroma_client()
        has, getres = tools.has_url(link, client=chromac)
        if has:
            tools.remove_url(link, client=chromac)

            await ctx.send("removal complete")
        else:
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

        chromac = ChromaTools.get_chroma_client()

        target_message = await ctx.send(
            f"<a:LoadingBlue:1206301904863502337> Retrieving {link} ..."
        )

        statmess = StatusEditMessage(target_message, ctx)
        async with ctx.channel.typing():
            hc, lines = await self.load_links(
                ctx, [link], chromac, statmess=None, override=True
            )
            embed = discord.Embed(
                title="Website Load Results",
                description=f"{1}/{1}\nout=\n{lines}",
            )
            embed.set_footer(text="Operation complete.")
            await statmess.editw(min_seconds=0, content=f"Overwrite ok.", embed=embed)

    @commands.is_owner()
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
    async def research(
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

        chromac = ChromaTools.get_chroma_client()
        res = await ctx.send("ok")
        statmess = StatusEditMessage(res, ctx)
        

        embed = discord.Embed(title=f"Search Query: {question} ")

        embed.add_field(name="Question", value=question, inline=False)
        if site_title_restriction != "None":
            embed.add_field(name="restrict", value=site_title_restriction, inline=False)
        await statmess.editw(min_seconds=0, content="querying db...", embed=embed)
        async with ctx.channel.typing():
            data = await tools.search_sim(
                question,
                client=chromac,
                titleres=site_title_restriction,
                k=k,
                mmr=use_mmr,
            )
            print(data)
            len(data)
            if len(data) <= 0:
                return "NO RELEVANT DATA."
            docs2 = sorted(data, key=lambda x: x[1], reverse=False)
            all_links=[doc.metadata.get("source",'???') for doc, e in docs2]
            links=set(doc.metadata.get("source",'???') for doc, e in docs2)
            def ie(all_links: List[str], value: str) -> List[int]:
                return [index for index, link in enumerate(all_links) if link == value]
            
            used="\n".join(f"{ie(all_links,l)}{l}" for l in links)
            fil = prioritized_string_split(used, ["%s\n"], 4000 )
            cont = '...' if len(fil)>2 else ""
            embed.description=f"{fil[0]}{cont}"
            embed.add_field(
                name="Cache_Query",
                value=f"About {len(docs2)} entries where found.  Max score is {docs2[0][1]}",
            )
            # docs2 = sorted(data, key=lambda x: x[1],reverse=True)
            await statmess.editw(
                min_seconds=0, content="drawing conclusion...", embed=embed
            )
            answer = await tools.format_answer(question, docs2)
            page = commands.Paginator(prefix="", suffix=None)
            viewme = Followup(bot=self.bot, page_content=docs2)
            for p in answer.split("\n"):
                page.add_line(p)
            messageresp = None
            for pa in page.pages:
                ms = await ctx.channel.send(pa)
                if messageresp == None:
                    messageresp = ms
            await ctx.channel.send("complete", view=viewme)
            
    @commands.is_owner()
    @commands.hybrid_command(
        name="researchpoint", description="Extract relevant information from the given source", extras={}
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

        chromac = ChromaTools.get_chroma_client()
        res = await ctx.send("ok")
        statmess = StatusEditMessage(res, ctx)
        embed = discord.Embed(title=f"Search Query: {question} ", description=f"ok")
        embed.add_field(name="Question", value=question, inline=False)
        if site_title_restriction != "None":
            embed.add_field(name="restrict", value=site_title_restriction, inline=False)
        await statmess.editw(min_seconds=0, content="querying db...", embed=embed)
        async with ctx.channel.typing():
            data = await tools.search_sim(
                question,
                client=chromac,
                titleres=site_title_restriction,
                k=k,
                mmr=use_mmr,
            )

            if len(data) <= 0:
                return "NO RELEVANT DATA."
            docs2 = sorted(data, key=lambda x: x[1], reverse=False)
            embed.add_field(
                name="Cache_Query",
                value=f"About {len(docs2)} entries where found.  Max score is {docs2[0][1]}",
            )
            # docs2 = sorted(data, key=lambda x: x[1],reverse=True)
            await statmess.editw(
                min_seconds=0, content="drawing conclusion...", embed=embed
            )
            answer = await tools.get_points(question, docs2)
            for a in answer:
                d,c=a
                emb=discord.Embed(title=d.metadata.get("title","?"), description=c)
                await ctx.send(embed=emb)


    @commands.command(name="titlecheck")
    @oai_check()
    @ai_rate_check()
    async def get_matching_titles(self, ctx, titleres):
        site_title_restriction = titleres
        chromac = ChromaTools.get_chroma_client()
        res = await ctx.send("ok")
        statmess = StatusEditMessage(res, ctx)

        question = "unimportant"

        await statmess.editw(
            min_seconds=0, content=f"querying db using `{titleres}`..."
        )
        async with ctx.channel.typing():
            data = await tools.debug_get(
                "not_important.", client=chromac, titleres=site_title_restriction
            )
            datas = zip(data["ids"], data["metadatas"])
            length = len(data)
            if length <= 0:
                await ctx.send("NO RELEVANT DATA.")
                return
            pages, found, keylen = [], {}, 0
            for e, pa in enumerate(datas):
                _, p = pa
                if p["source"] not in found:
                    found[p["source"]] = [0, str(p)[:4000]]
                    keylen += 1
                found[p["source"]][0] += 1
                await statmess.editw(
                    min_seconds=4, content=f"Filtering results {e}/{length}"
                )
            await statmess.editw(
                min_seconds=0,
                content=f"**Results found:** {length}"
                + "\n"
                + f"Sorted into {keylen} buckets.",
            )
            for _, v in found.items():
                e = discord.Embed(description=v[1])
                e.add_field(name="values:", value=f"count:{v[0]}")
                pages.append(e)
            await pages_of_embeds(ctx, pages, ephemeral=True)

    @commands.command(name="get_source", description="get sources.", extras={})
    @oai_check()
    async def source_get(self, ctx: commands.Context, question: str):
        chromac = ChromaTools.get_chroma_client()
        data = await tools.search_sim(question, client=chromac, titleres="None")
        len(data)
        if len(data) <= 0:
            await ctx.send("NO RELEVANT DATA.")
        docs2 = sorted(data, key=lambda x: x[1], reverse=False)
        embed = discord.Embed(title="sauces")
        for doc, score in docs2[:10]:
            # print(doc)
            # 'metadata',{'title':'UNKNOWN','source':'unknown'})
            meta = doc.metadata
            content = doc.page_content  # ('page_content','Data l
            output = f"""**Name:** {meta['title'][:100]}
            **Link:** {meta['source']}
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
        **Name:** {meta['title']}
        **Link:** {meta['source']}
        **Text:** {content}"""
            embed.add_field(name=f"s: score:{score}", value=output[:1020], inline=False)
            field_count += 1
        embeds.append(embed)
        pcc, buttons = await pages_of_embeds_2("ANY", embeds)

        await ctx.channel.send(embed=pcc.make_embed(), view=buttons)
        # viewme=Followup(bot=self.bot,page_content=docs2)
        # await ctx.channel.send(f'{len(data)} sources found',view=viewme)

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

        targetmessage = await context.send(content=f"Translating...")

        res = await bot.gptapi.callapi(chat)
        # await ctx.send(res)
        print(res)
        result = res["choices"][0]["message"]["content"]
        embeds = []
        pages = commands.Paginator(prefix="", suffix="", max_size=2000)
        for l in result.split("\n"):
            pages.add_line(l)
        for e, p in enumerate(pages.pages):
            embed = discord.Embed(
                title=f"Translation" if e == 0 else f"Translation {e+1}", description=p
            )
            embeds.append(embed)

        await targetmessage.edit(content=text, embed=embeds[0])
        for e in embeds[1:]:
            await context.send(embed=e)

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
        returnme = await ctx.send(content=comment + "{code[:1024]}", embed=emb)
        return returnme

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
                f"<a:LoadingBlue:1206301904863502337> Reading Article <a:LoadingBlue:1206301904863502337>"
            )
            try:
                async with ctx.channel.typing():
                    article, header = await read_article_async(ctx.bot.jsenv, url)
            except Exception as e:
                await mes.edit(content="I couldn't read the link, sorry.  It might be too large.")
                raise e;
            await mes.delete()
            def filter_inline_links(markdown_string):
                return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", markdown_string)

            filtered_markdown = article
            if filter_links:
                filtered_markdown = filter_inline_links(article)
                print(filtered_markdown)

            splitorder = [("\n## %s", 1000), ("\n### %s", 4000), ("%s\n", 4000)]
            fil = prioritized_string_split(filtered_markdown, splitorder)

            mytitle = header.get("title", "notitle")
            await ctx.send(f"# {mytitle}")
            length = len(fil)
            embeds=[]
            for e, d in enumerate(fil):
                use = d
                if escape_markdown:
                    use = discord.utils.escape_markdown(d)
                emb = discord.Embed(title=f"{mytitle}: {e}/{length}", description=use)
                embeds.append(emb)
            if len(embeds)>5:
                message=await pages_of_embeds(ctx,display=embeds)
            else:
                for e in embeds: await ctx.send(embed=e)


    @commands.command(
        name="summarize", description="make a summary of a url.", extras={}
    )
    @oai_check()
    @ai_rate_check()
    async def summarize(
        self, ctx: commands.Context, url: str, over: bool = False, stopat: str = None
    ):
        """Download the reader mode view of a passed in URL, and summarize it."""
        async with self.lock:
            message = ctx.message
            guild = message.guild
            user = message.author

            mes = await ctx.channel.send(
                f"<a:LoadingBlue:1206301904863502337> Reading Article <a:LoadingBlue:1206301904863502337>"
            )
            try:
                article, header = await read_article(ctx.bot.jsenv, url)
            except Exception as e:
                await mes.edit(content="I couldn't read the link, sorry.  It might be too large.")
                raise e;
            await mes.delete()
            if stopat != None:
                article = article.split(stopat)[0]
            chat = gptmod.ChatCreation(
                messages=[{"role": "system", "content": self.prompt}],
                model="gpt-3.5-turbo-0125",
            )
            chat.add_message(role="user", content=article)
            sources = []

            mylinks = extract_masked_links(article)
            for link in mylinks:
                link_text, url4 = link
                link_text = link_text.replace("_", "")
                print(link_text, url4)
                sources.append(f"[{link_text}]({url4})")

            # Call API
            bot = ctx.bot
            async with ctx.channel.typing():
                try:
                    res = await bot.gptapi.callapi(chat)

                    # await ctx.send(res)
                    print("clear", res)

                    result = res.choices[0].message.content
                    print(result)
                    for link in mylinks:
                        link_text, url2 = link
                        link_text = link_text.replace("_", "")
                        print(link_text, url2)
                        if link_text in result:
                            print(link_text, url2)
                            # sources.append(f"[{link_text}]({url})")
                            result = result.replace(link_text, f"{link_text}")
                    splitorder = ["%s\n", "%s.", "%s,", "%s "]
                    fil = prioritized_string_split(result, splitorder, 4072)
                    for p in fil:
                        embed = discord.Embed(
                            title=header.get("title", "notitle"), description=p
                        )
                        await ctx.send(
                            content=header.get("title", "notitle")[:200], embed=embed
                        )
                    embed = discord.Embed(
                        title=f"Sources for {header.get('title', 'notitle')}"
                    )
                    name, res = "", ""
                    if len(sources) < 20:
                        fil = prioritized_string_split(
                            "\n".join(sources), ["%s\n"], 1020
                        )
                        needadd = False
                        for e, i in enumerate(fil):
                            embed.add_field(
                                name=f"Sources Located: {e}", value=i, inline=False
                            )
                            needadd = True
                            if (e + 1) % 6 == 0:
                                await ctx.send(embed=embed)
                                needadd = False
                                embed = discord.Embed(
                                    title=f"Sources for {header.get('title', 'notitle')}"
                                )
                        if needadd:
                            await ctx.send(
                                content=header.get("title", "???"), embed=embed
                            )
                    if over:
                        target_message = await ctx.send(
                            f"<a:LoadingBlue:1206301904863502337> Saving {url} summary..."
                        )
                        chromac = ChromaTools.get_chroma_client()
                        await tools.add_summary(url, result, header, client=chromac)
                        await target_message.edit(content="SUMMARY SAVED!")
                except Exception as e:
                    await ctx.bot.send_error(e)
                    return await ctx.send(e)
    @commands.command(
        name="summarize_db", description="make a summary of a url.", extras={}
    )
    @oai_check()
    @ai_rate_check()
    async def summarize_db(
        self, ctx: commands.Context, url: str, over: bool = False, stopat: str = None
    ):
        """Generate a summary of an already loaded source."""
        async with self.lock:
            message = ctx.message
            mes = await ctx.channel.send(
                f"<a:LoadingBlue:1206301904863502337> Reading Article <a:LoadingBlue:1206301904863502337>"
            )
            client = ChromaTools.get_chroma_client()
            article = ""
            collectionvar = client.get_collection('web_collection')
            res = collectionvar.get(
                where={"source": url}, include=["metadatas", 'documents']
            )
            out = zip(res['metadatas'], res['documents'])
            out = sorted(out, key=lambda x: x[0]['split'])
            header=res['metadatas'][0]
            for c in out:
                article += c[1] + "\n"
            await mes.delete()
            if stopat is not None:
                article = article.split(stopat)[0]
            chat = gptmod.ChatCreation(
                messages=[{"role": "system", "content": self.prompt}],
                model="gpt-3.5-turbo-0125",
            )
            chat.add_message(role="user", content=article)
            # Call API
            bot = ctx.bot
            async with ctx.channel.typing():
                res = await bot.gptapi.callapi(chat)
                result = res.choices[0].message.content
                splitorder = ["%s\n", "%s.", "%s,", "%s "]
                fil = prioritized_string_split(result, splitorder, 4072)
                for p in fil:
                    embed = discord.Embed(
                        title=header.get("title", "notitle"), description=p
                    )
                    await ctx.send(embed=embed)
                if over:
                    target_message = await ctx.send(
                        f"<a:LoadingBlue:1206301904863502337> Saving {url} summary..."
                    )
                    chromac = ChromaTools.get_chroma_client()
                    await tools.add_summary(url, result, header, client=chromac)
                    await target_message.edit(content="SUMMARY SAVED!")


async def setup(bot):
    await bot.add_cog(ResearchCog(bot))
