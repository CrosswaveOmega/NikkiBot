import discord
import asyncio
from assets import AssetLookup
import re

# import datetime


from discord.ext import commands

from discord import app_commands
from bot import TC_Cog_Mixin, StatusEditMessage, super_context_menu
import gptmod
from gptfunctionutil import *
import gptmod.error
from database.database_ai import AuditProfile

# I need the readability npm package to work, so
from javascriptasync import require, eval_js
import assets
import gui
from .ResearchAgent import *
from googleapiclient.discovery import build  # Import the library


# def is_readable(url):
#     timeout = 30
#     readability = require("@mozilla/readability")
#     jsdom = require("jsdom")
#     TurndownService = require("turndown")
#     # Is there a better way to do this?
#     print("attempting parse")
#     out = f"""
#     let result=await check_read(`{url}`,readability,jsdom);
#     return result
#     """
#     myjs = assets.JavascriptLookup.find_javascript_file("readwebpage.js", out)
#     # myjs=myjs.replace("URL",url)
#     print(myjs)
#     rsult = eval_js(myjs)
#     return rsult




async def read_article_async(jsctx, url, clearout=True):
    myfile=await assets.JavascriptLookup.get_full_pathas('readwebpage.js','WEBJS',jsctx)
    print(url)
    rsult = await myfile.read_webpage_plain(url, timeout=45)
    #print(rsult)
    output= await rsult.get_a('mark')
    header=await rsult.get_a('orig')
    serial=await header.get_dict_a()
    #print(serial)
    simplified_text = output.strip()
    simplified_text = simplified_text.replace("*   ","* ")
    if clearout:
        simplified_text = re.sub(r"(\n){4,}", "\n\n\n", simplified_text)
        simplified_text = re.sub(r"\n\n", "\n", simplified_text)
        
        simplified_text = re.sub(r" {3,}", "  ", simplified_text)
        simplified_text = simplified_text.replace("\t", "")
        simplified_text = re.sub(r"\n+(\s*\n)*", "\n", simplified_text)
    #print(simplified_text)
    return simplified_text, serial

async def read_article(jsctx,url):
    now = discord.utils.utcnow()
    result = await read_article_async(jsctx,url)
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
    """For Timers."""

    def __init__(self, bot):
        self.helptext = "This cog is for AI powered websearch and summarization."
        self.bot = bot
        self.lock = asyncio.Lock()
        self.prompt = """
        Summarize general news articles, forum posts, and wiki pages that have been converted into Markdown. Condense the content into 2-4 medium-length paragraphs with 3-7 sentences per paragraph. Preserve key information and maintain a descriptive tone. The summary should be easily understood by a 10th grader. Exclude any concluding remarks from the summary.
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
        if await context.bot.gptapi.check_oai(context):
            return

        serverrep, userrep = AuditProfile.get_or_new(guild, user)
        userrep.checktime()
        ok, reason = userrep.check_if_ok()
        if not ok:
            if reason in ["messagelimit", "ban"]:
                await context.send("You have exceeded daily rate limit.")
                return
        userrep.modify_status()
        chat = gptmod.ChatCreation(
            messages=[{"role": "system", "content": self.translationprompt}]
        )

        totranslate = message.content
        if message.embeds:
            for m in message.embeds:
                result = extract_embed_text(m)
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
        limit: int = 5,
    ):
        "Search google for a query."
        bot = ctx.bot
        if "google" not in bot.keys or "cse" not in bot.keys:
            return "insufficient keys!"
        query_service = build("customsearch", "v1", developerKey=bot.keys["google"])
        query_results = (
            query_service.cse()
            .list(q=query, cx=bot.keys["cse"], num=limit)  # Query  # CSE ID
            .execute()
        )
        results = query_results["items"]
        allstr = ""
        emb = discord.Embed(title="Search results", description=comment)
        readable_links = []
        messages = ctx.send("Search completed, indexing.")
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

    @AILibFunction(
        name="google_detective",
        description="Solve a question using a google search.  Form the query based on the question, and then use the page text from the search results to create an answer..",
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
        if not ctx.guild:
            await ctx.send("needs to be guild")
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(
                "I'm sorry, but the research system is unavailable in this server."
            )
            return "INVALID CONTEXT"
        if "google" not in bot.keys or "cse" not in bot.keys:
            await ctx.send("google search keys not set up.")
            return "insufficient keys!"
        serverrep, userrep = AuditProfile.get_or_new(ctx.guild, ctx.author)
        serverrep.checktime()
        userrep.checktime()

        ok, reason = userrep.check_if_ok()
        if not ok:
            if reason in ["messagelimit", "ban"]:
                await ctx.channel.send("You have exceeded daily rate limit.")
                return
        chromac = ChromaTools.get_chroma_client()

        target_message = await ctx.channel.send(
            f"<a:SquareLoading:1143238358303264798> Searching google for {query} ..."
        )

        statmess = StatusEditMessage(target_message, ctx)
        current=""
        async with ctx.channel.typing():
            results = google_search(ctx.bot, query, result_limit)

            all_links = []
            hascount = 0
            length = len(results)
            lines = "\n".join([f"- {r['link']}" for r in results])

            embed = discord.Embed(title=f"query: {query}", description=f"out=\n{lines}")

            await statmess.editw(
                min_seconds=0,
                content=f"<a:LetWalkR:1118191001731874856> Search complete: reading {0}/{length}. {hascount}/{len(all_links)}",
                embed=embed,
            )
            for e, r in enumerate(results):
                all_links.append(r["link"])
                embed = discord.Embed(description=f"out=\n{lines}")
                has, getres = has_url(r["link"], client=chromac)
                if has:
                    current+=f"[Link {e}]({r['link']}) has{len(getres['documents'])} cached documents.\n"
                    await statmess.editw(
                        min_seconds=5,
                        content=f"<a:LetWalkR:1118191001731874856> {current}",
                        embed=embed,
                    )
                    ver = zip(getres["documents"], getres["metadatas"])
                    for d, e in ver:
                        if e["source"] != r["link"]:
                            await ctx.send(f"docmismatch MISMATCH")
                    hascount += 1
                else:
                    try:
                        splits = await read_and_split_link(ctx.bot,r["link"])
                        dbadd = True
                        for split in splits:
                            gui.gprint(split.page_content)
                            for i, m in split.metadata.items():
                                gui.gprint(i, m)
                                if m == None:
                                    split.metadata[i] = "N/A"
                                else:
                                    dbadd = True
                        if dbadd:
                            current+=f"[Link {e}]({r['link']}) has {len(splits)} splits.\n"
                            await statmess.editw(
                                min_seconds=5,
                                content=f"<a:LetWalkR:1118191001731874856> {current}",
                                embed=embed,
                            )
                            store_splits(splits, client=chromac)
                    except Exception as err:
                       current+=f"{str(err)}"
                       await statmess.editw(
                            min_seconds=5,
                            content=f"<a:LetWalkR:1118191001731874856> {current}",
                            embed=embed,
                        )
                       await bot.send_error(err)


        lines = "\n".join(all_links)
        embed = discord.Embed(
            title=f"Search Query: {query} ",
            description=f"{hascount}/{len(all_links)}\nout=\n{lines}",
        )
        embed.add_field(name="Question", value=question, inline=False)
        if site_title_restriction != "None":
            embed.add_field(name="restrict", value=site_title_restriction, inline=False)
        embed.set_footer(text=comment)
        await statmess.editw(min_seconds=0, content="querying db...", embed=embed)
        async with ctx.channel.typing():
            data = await search_sim(
                question, client=chromac, titleres=site_title_restriction
            )
            len(data)
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
            answer = await format_answer(question, docs2)
            page = commands.Paginator(prefix="", suffix=None)
            viewme = Followup(bot=self.bot, page_content=docs2)
            for p in answer.split("\n"):
                page.add_line(p)
            messageresp = None
            pages=[p for p in page.pages]
            pl=len(pages)
            for e,pa in enumerate(pages):
                if e==pl-1:
                    ms = await ctx.channel.send(pa,view=viewme)
                else:
                    ms = await ctx.channel.send(pa)
                if messageresp is None:
                    messageresp = ms
            #await ctx.channel.send("complete", view=viewme)
            return messageresp

    @commands.command(name="loadurl", description="loadurl test.", extras={})
    async def loader_test(self, ctx: commands.Context, link: str):
        async with ctx.channel.typing():
            splits = await read_and_split_link(ctx.bot,link)
        await ctx.send(
            f"[Link ]({link}) has {len(splits)} splits.", suppress_embeds=True
        )
        for i in splits[0:3]:
            await ctx.send(f"```{str(i.page_content)}```"[:1980], suppress_embeds=True)

    @commands.is_owner()
    @commands.command(name="loadmany")
    async def loadmany(self, ctx: commands.Context, links: str):
        """'replace a url in documents.
        link:str
        """
        bot = ctx.bot
        if not ctx.guild:
            await ctx.send("needs to be guild")
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(
                "I'm sorry, but the research system is unavailable in this server."
            )
            return "INVALID CONTEXT"
        if "google" not in bot.keys or "cse" not in bot.keys:
            await ctx.send("google search keys not set up.")
            return "insufficient keys!"
        serverrep, userrep = AuditProfile.get_or_new(ctx.guild, ctx.author)
        serverrep.checktime()
        userrep.checktime()

        ok, reason = userrep.check_if_ok()
        if not ok:
            if reason in ["messagelimit", "ban"]:
                await ctx.channel.send("You have exceeded daily rate limit.")
                return
        chromac = ChromaTools.get_chroma_client()
        for link in links.split("\n"):
            target_message = await ctx.send(
                f"<a:SquareLoading:1143238358303264798> Retrieving {link} ..."
            )

            statmess = StatusEditMessage(target_message, ctx)
            async with ctx.channel.typing():
                results = [{"link": link}]

                all_links = []
                hascount = 0
                length = len(results)
                lines = "\n".join([f"- {r['link']}" for r in results])

                embed = discord.Embed(
                    title=f"query: {link}.", description=f"out=\n{lines}"
                )

                await statmess.editw(
                    min_seconds=0,
                    content=f"<a:SquareLoading:1143238358303264798> Retrieving {link} ...",
                    embed=embed,
                )
                for e, r in enumerate(results):
                    all_links.append(r["link"])
                    embed = discord.Embed(description=f"out=\n{lines}")
                    has, getres = has_url(r["link"], client=chromac)
                    if has:
                        await ctx.send("removing present entries for new data...")
                        remove_url(r["link"], client=chromac)
                    splits = await read_and_split_link(ctx.bot,r["link"])
                    dbadd = True
                    for split in splits:
                        gui.gprint(split.page_content)
                        for i, m in split.metadata.items():
                            gui.gprint(i, m)
                            if m == None:
                                split.metadata[i] = "N/A"
                            else:
                                dbadd = True
                                # await ctx.send(f"split metadata {i} is none!")
                    if dbadd:
                        await ctx.send(
                            f"[Link {e}]({r['link']}) has {len(splits)} splits.",
                            suppress_embeds=True,
                        )
                        store_splits(splits, client=chromac)
                    # await statmess.editw(min_seconds=15,content=f'reading {e}/{length}. {hascount}/{len(all_links)}',embed=embed)
                await statmess.editw(
                    min_seconds=0, content=f"Overwrite ok.", embed=embed
                )

    @commands.is_owner()
    @commands.hybrid_command(
        name="loadurlover",
        description="replace or load a url into my document_store documents.",
        extras={},
    )
    @app_commands.describe(link="URL to add to my database.")
    async def loadover(self, ctx: commands.Context, link: str):
        """'replace a url in documents.
        link:str
        """
        bot = ctx.bot
        if not ctx.guild:
            await ctx.send("needs to be guild")
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(
                "I'm sorry, but the research system is unavailable in this server."
            )
            return "INVALID CONTEXT"
        if "google" not in bot.keys or "cse" not in bot.keys:
            await ctx.send("google search keys not set up.")
            return "insufficient keys!"
        serverrep, userrep = AuditProfile.get_or_new(ctx.guild, ctx.author)
        serverrep.checktime()
        userrep.checktime()

        ok, reason = userrep.check_if_ok()
        if not ok:
            if reason in ["messagelimit", "ban"]:
                await ctx.channel.send("You have exceeded daily rate limit.")
                return
        chromac = ChromaTools.get_chroma_client()

        target_message = await ctx.send(
            f"<a:SquareLoading:1143238358303264798> Retrieving {link} ..."
        )

        statmess = StatusEditMessage(target_message, ctx)
        async with ctx.channel.typing():
            results = [{"link": link}]

            all_links = []
            hascount = 0
            length = len(results)
            lines = "\n".join([f"- {r['link']}" for r in results])

            embed = discord.Embed(title=f"query: {link}.", description=f"out=\n{lines}")

            await statmess.editw(
                min_seconds=0,
                content=f"<a:SquareLoading:1143238358303264798> Retrieving {link} ...",
                embed=embed,
            )
            for e, r in enumerate(results):
                all_links.append(r["link"])
                embed = discord.Embed(description=f"out=\n{lines}")
                has, getres = has_url(r["link"], client=chromac)
                if has:
                    await ctx.send("removing present entries for new data...")
                    remove_url(r["link"], client=chromac)
                splits = await read_and_split_link(ctx.bot,r["link"])
                dbadd = True
                for split in splits:
                    gui.gprint(split.page_content)
                    for i, m in split.metadata.items():
                        gui.gprint(i, m)
                        if m == None:
                            split.metadata[i] = "N/A"
                        else:
                            dbadd = True
                            # await ctx.send(f"split metadata {i} is none!")
                if dbadd:
                    await ctx.send(
                        f"[Link {e}]({r['link']}) has {len(splits)} splits.",
                        suppress_embeds=True,
                    )
                    store_splits(splits, client=chromac)
                # await statmess.editw(min_seconds=15,content=f'reading {e}/{length}. {hascount}/{len(all_links)}',embed=embed)
            await statmess.editw(min_seconds=0, content=f"Overwrite ok.", embed=embed)

    @commands.is_owner()
    @commands.hybrid_command(
        name="researchcached", description="Research a topic.", extras={}
    )
    @app_commands.guilds(int(target_server[1]))
    @app_commands.describe(question="question to be asked.")
    @app_commands.describe(k="min number of sources to grab.")
    @app_commands.describe(
        site_title_restriction="Restrain query to websites with this in the title."
    )
    async def research(
        self,
        ctx: commands.Context,
        question: str,
        k: int = 5,
        site_title_restriction: str = "None",
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
            await ctx.send(
                "I'm sorry, but the research system is unavailable in this server."
            )
            return "INVALID CONTEXT"

        serverrep, userrep = AuditProfile.get_or_new(ctx.guild, ctx.author)
        serverrep.checktime()
        userrep.checktime()

        ok, reason = userrep.check_if_ok()
        if not ok:
            if reason in ["messagelimit", "ban"]:
                await ctx.channel.send("You have exceeded daily rate limit.")
                return
        chromac = ChromaTools.get_chroma_client()
        res = await ctx.send("ok")
        statmess = StatusEditMessage(res, ctx)
        embed = discord.Embed(title=f"Search Query: {question} ", description=f"ok")
        embed.add_field(name="Question", value=question, inline=False)
        if site_title_restriction != "None":
            embed.add_field(name="restrict", value=site_title_restriction, inline=False)
        await statmess.editw(min_seconds=0, content="querying db...", embed=embed)
        async with ctx.channel.typing():
            data = await search_sim(
                question, client=chromac, titleres=site_title_restriction, k=k
            )
            print(data)
            len(data)
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
            answer = await format_answer(question, docs2)
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

    @commands.command(name="titecheck")
    async def get_matching_titles(self, ctx, titleres):
        if not ctx.guild:
            await ctx.send("needs to be guild")
            return
        if await ctx.bot.gptapi.check_oai(ctx):
            await ctx.send(
                "I'm sorry, but the research system is unavailable in this server."
            )
            return "INVALID CONTEXT"

        serverrep, userrep = AuditProfile.get_or_new(ctx.guild, ctx.author)
        serverrep.checktime()
        userrep.checktime()

        question = "unimportant"
        site_title_restriction = titleres
        ok, reason = userrep.check_if_ok()
        if not ok:
            if reason in ["messagelimit", "ban"]:
                await ctx.channel.send("You have exceeded daily rate limit.")
                return
        chromac = ChromaTools.get_chroma_client()
        res = await ctx.send("ok")
        statmess = StatusEditMessage(res, ctx)
        embed = discord.Embed(title=f"Search Query: {question} ", description=f"ok")
        embed.add_field(name="Question", value=question, inline=False)
        if site_title_restriction != "None":
            embed.add_field(name="restrict", value=site_title_restriction, inline=False)
        await statmess.editw(min_seconds=0, content="querying db...", embed=embed)
        async with ctx.channel.typing():
            data = await debug_get(
                question, client=chromac, titleres=site_title_restriction
            )
            len(data)
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
            answer = "NO ANSWER"
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

    @commands.command(name="get_source", description="get sources.", extras={})
    async def source_get(self, ctx: commands.Context, question: str):
        chromac = ChromaTools.get_chroma_client()
        data = await search_sim(question, client=chromac, titleres="None")
        len(data)
        if len(data) <= 0:
            await ctx.send("NO RELEVANT DATA.")
        docs2 = sorted(data, key=lambda x: x[1], reverse=False)
        embed = discord.Embed(title="sauces")
        for doc, score in docs2[:10]:
            # print(doc)
            meta = doc.metadata  #'metadata',{'title':'UNKNOWN','source':'unknown'})
            content = doc.page_content  # ('page_content','Data l
            output = f"""**Name:** {meta['title'][:100]}
            **Link:** {meta['source']}
            **Text:** {content[:256]}..."""
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
            output = f"""**Name:** {meta['title'][:100]}
            **Link:** {meta['source']}
            **Text:** {content}"""
            embed.add_field(name=f"s: score:{score}", value=output[:1020], inline=False)
            field_count += 1
        embeds.append(embed)
        PCC, buttons = await pages_of_embeds_2("ANY", embeds)

        await ctx.channel.send(embed=PCC.make_embed(), view=buttons)
        # viewme=Followup(bot=self.bot,page_content=docs2)
        # await ctx.channel.send(f'{len(data)} sources found',view=viewme)

    @commands.hybrid_command(
        name="translate_simple", description="Translate a block of text."
    )
    async def translatesimple(self, context, text: str):
        if not context.guild:
            return
        if await context.bot.gptapi.check_oai(context):
            return
        guild, user = context.guild, context.author
        serverrep, userrep = AuditProfile.get_or_new(guild, user)
        userrep.checktime()
        ok, reason = userrep.check_if_ok()
        if not ok:
            if reason in ["messagelimit", "ban"]:
                await context.send("You have exceeded daily rate limit.")
                return
        userrep.modify_status()
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
    async def webreader(self, ctx: commands.Context, url: str, filter_links:bool=False,escape_markdown:bool=False):
        """Download the text from a website, and read it"""
        async with self.lock:
            message = ctx.message
            guild = message.guild
            user = message.author
            article, header = await read_article_async(ctx.bot.jsenv,url,False)



            def filter_inline_links(markdown_string):
                return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', markdown_string)

            filtered_markdown=article
            if filter_links:
                filtered_markdown = filter_inline_links(article)
                print(filtered_markdown)

            splitorder=['\n## ','\n### ','\n']
            #docs=await split_link([filtered_markdown],chunk_size=2000)
            fil=[filtered_markdown]
            for s in splitorder:
                newsplit=[]
                for old in fil:
                    pages = commands.Paginator(prefix="", suffix="",max_size=2000)
                    for p in old.split(s):
                        pages.add_line(p)
                    for e,d in enumerate(pages.pages):
                        newsplit.append(d)
                fil=newsplit
            mytitle=header.get('title', "notitle")
            await ctx.send(f"# {mytitle}")
            length=len(fil)
            for e,d in enumerate(fil):
                use=d
                if escape_markdown:
                    use=discord.utils.escape_markdown(d)
                emb=discord.Embed(
                    title=f"{mytitle}: {e}/{length}",
                    description=use
                )
                await ctx.send(embed=emb)

    @commands.command(
        name="summarize", description="make a summary of a url.", extras={}
    )
    async def summarize(
        self, ctx: commands.Context, url: str, over: bool = False, stopat: str = None
    ):
        """Download the reader mode view of a passed in URL, and summarize it."""
        async with self.lock:
            message = ctx.message
            guild = message.guild
            user = message.author

            if await ctx.bot.gptapi.check_oai(ctx):
                return
            serverrep, userrep = AuditProfile.get_or_new(guild, user)
            serverrep.checktime()
            userrep.checktime()

            ok, reason = userrep.check_if_ok()
            if not ok:
                if reason in ["messagelimit", "ban"]:
                    await ctx.channel.send("You have exceeded daily rate limit.")
                    return
            mes = await ctx.channel.send(
                f"<a:SquareLoading:1143238358303264798> Reading Article"
            )
            serverrep.modify_status()
            userrep.modify_status()
            article, header = await read_article(ctx.bot.jsenv,url)
            if stopat != None:
                article = article.split(stopat)[0]
            chat = gptmod.ChatCreation(
                messages=[{"role": "system", "content": self.prompt}],
                model="gpt-3.5-turbo-1106",
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
            messageresp = None
            await mes.delete()
            async with ctx.channel.typing():
                try:
                    res = await bot.gptapi.callapi(chat)

                    # await ctx.send(res)
                    print('clear',res)
                    
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
                    page = commands.Paginator(prefix="", suffix=None, max_size=4000)

                    for p in result.split("\n"):
                        page.add_line(p)
                    for p in page.pages:
                        embed = discord.Embed(title=header.get('title', "notitle"), description=p)
                        await ctx.send(content=header.get('title', "notitle")[:200], embed=embed)
                    embed = discord.Embed()
                    name, res = "", ""
                    if len(sources) < 20:
                        for i in sources:
                            if len(res + i) > 1020:
                                embed.add_field(
                                    name="Sources Located", value=res, inline=False
                                )
                                res = ""
                                await ctx.send(content=header.get('title', "notitle"), embed=embed)
                                embed = discord.Embed()
                            res += f"{i}\n"
                        embed.add_field(name="Sources Located", value=res, inline=False)

                        await ctx.send(content=header.get('title',"???"), embed=embed)
                    if over:
                        target_message = await ctx.send(
                            f"<a:SquareLoading:1143238358303264798> Saving {url} summary..."
                        )
                        chromac = ChromaTools.get_chroma_client()
                        await add_summary(url, result, header, client=chromac)
                        await target_message.edit(content="SUMMARY SAVED!")
                except Exception as e:
                    return await ctx.send(e)


async def setup(bot):
    await bot.add_cog(ResearchCog(bot))
