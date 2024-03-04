from typing import List, Tuple, Optional, Set, Dict, Any
import chromadb
import discord
import asyncio
from assets import AssetLookup
import re
import openai

# import datetime
import json
from io import StringIO

from discord.ext import commands

from discord import app_commands
from bot import TC_Cog_Mixin, StatusEditMessage, super_context_menu, TCBot

import gptfunctionutil.functionlib as gptum
from gptfunctionutil import SingleCall, SingleCallAsync
from .chromatools import ChromaTools,DocumentScoreVector
from .LinkLoader import SourceLinkLoader
from utility import urltomessage
from langchain.docstore.document import Document
import cogs.ResearchAgent.actions as actions
"""
This special context class is for the research commands.
"""


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
        return query, question, comment


class ResearchContext:
    def __init__(
        self,
        cog,
        ctx: commands.Context,
        k: int = 5,
        site_title_restriction: str = "None",
        use_mmr: bool = False,
        depth: int = 1,
        followup: int = 2,
        search_web: int = 0,
    ) -> None:
        self.cog = cog
        self.ctx = ctx
        self.k = k
        self.site_title_restriction = site_title_restriction
        self.use_mmr = use_mmr
        self.depth = depth
        self.followup = followup
        self.search_web = search_web

        self.bot: TCBot = ctx.bot

        self.all_runs = sum(self.followup**i for i in range(self.depth))
        self.res: Optional[discord.Message] = None
        self.channel: discord.TextChannel = ctx.channel
        self.statmess: Optional[StatusEditMessage] = None
        self.client: Optional[openai.AsyncClient] = None
        self.stack: List[Tuple[str, str, int, discord.Message]] = []
        self.answered: List[str] = []
        self.alllines: Set[str] = set()
        self.results: Dict[str, Any] = {}
        self.pending: Set[str] = set()

    def add_to_stack(
        self, question: str, cont: str, dep: int, message: discord.Message
    ):
        """
        Adds the given parameters to the internal pending stack.
        """
        self.pending.add(question)
        self.stack.append((question, cont, dep, message))

    async def send_preview(self):
        self.preview=await self.ctx.send("Preview")

    async def setup(self) -> bool:
        '''
        Preform an asyncronous check of the internal results.
        '''
        if not self.ctx.guild:
            await self.ctx.send("needs to be guild")
            return False
        if await self.ctx.bot.gptapi.check_oai(self.ctx):
            await self.ctx.send("INVALID SERVER ERROR")
            return False
        if 0 >= self.depth or self.depth > 5:
            await self.ctx.send("Depth is too high error.")
            return False
        if 0 >= self.followup or self.followup > 5:
            await self.ctx.send("Followup questions are too high.")
            return False
        if 0 > self.search_web or self.search_web > 10:
            await self.ctx.send("Invalid searchweb term.")
            return False
        if self.all_runs > 50:
            await self.ctx.send("Too many runs! Lower your followup or depth.")
            return False

        self.res = await self.ctx.send(
            f"<a:LoadingBlue:1206301904863502337>{len(self.stack)}/{self.all_runs} "
        )
        self.statmess = StatusEditMessage(self.res, self.ctx)
        self.client = openai.AsyncClient()

        return True
    
    async def get_query_from_question(self,quest:str) -> Tuple[str, str, str]:
        """Given a question, generate a searchable query"""
        querytuple: Optional[Tuple[Any, ...]] = None
        tries: int = 0
        
        while querytuple is None and tries < 3:
            try:
                lib = Followups()
                sc = SingleCallAsync(
                    mylib=lib,
                    model="gpt-3.5-turbo-0125",
                    client=self.client,
                    timeout=30,
                )
                querytuple = await sc.call_single(f"{quest}", "google_search")
            except Exception as e:
                await self.ctx.send("Retrying...")
                tries += 1
                if tries >= 3:
                    await self.ctx.send(f"{json.dumps(lib.get_tool_schema())}"[:1800])
                    raise e
        query, question, comment = querytuple[0][1]["content"]
        return (query, question, comment)
    
    async def websearch(self, questtup: Tuple[str, str, str]) -> Tuple[List[str], List[Dict]]:
        """
        Perform a web search based on the given query tuple and return a tuple containing links and results.

        Parameters:
        questtup (Tuple[str, str, str]): A tuple containing the query, question, and comment.

        Returns:
        Tuple[List[str], Dict]: A tuple containing a list of links and dictionaries with additional details.
        """
        #Preform web search.
        links, res = await self.cog.web_search(
            self.ctx, questtup[0], result_limit=self.search_web
        )
        return links, res

    async def load_links(self,questtup: Tuple[str, str, str],links:List[str],res:List[Dict[str, str]]=[]):
        """
        Load links into the system and update the corresponding status message with the results.

        Parameters:
        questtup (Tuple[str, str, str]): A tuple containing the query, question, and comment used for the search.
        links (List[str]): A list of links returned from the web search.
        res (List[Dict[str, str]]): A list of dictionaries containing the search results.
        """
        chromac = ChromaTools.get_chroma_client()
        #create status message for load_links.
        embed = discord.Embed(
            title=f"Web Search Results for: {questtup[0]} ",
        )
        for v in res:
            embed.add_field(name=v["title"], value=v["desc"], inline=True)
        target_message = await self.ctx.send(embed=embed)

        statmess = StatusEditMessage(target_message, self.ctx)
        loader = SourceLinkLoader(chromac=chromac, statusmessage=statmess,embed=embed)
        _, lines = await loader.load_links(self.ctx, links, False)
        await statmess.delete()
        s = lines.split("\n")
        for e in s:
            se = e.split(" ")
            if se[0] == "<:add:1199770854112890890>":
                self.alllines.add(se[1])

    async def research(self, quest: str) -> Tuple[str, List[str], List[DocumentScoreVector]]:
        """
        Queries the database for relevant documents and formats an answer to the user's question.

        Parameters:
        - quest (str): The user's query/question.

        Returns:
        - Tuple[str, List[str], discord.Message]: A tuple containing the formatted answer, 
             list of document links, and a sent discord message pertaining to the results.
        """
        res = await self.ctx.send("<a:LoadingBlue:1206301904863502337> querying db...")
        statmess = StatusEditMessage(res, self.ctx)
        answer, links, docs = await actions.research_op(
            quest,
            k=self.k,
            site_title_restriction=self.site_title_restriction,
            use_mmr=self.use_mmr,
            statmess=statmess
        )
        return answer, links, docs
    
    async def format_results(
        self,
        quest: str,
        qatup: Tuple[str, str, str],
        answer: str,
        parent: Optional[discord.Message] = None,
    ) -> Tuple[discord.Embed, discord.Message]:
        '''Generates and sends a Discord message embed containing the supplied question and answer.

        Args:
            quest (str): The initial question that prompted the research.
            qatup (Tuple[str, str, str]): A tuple containing the query used for research, the reformulated question, and an accompanying comment.
            answer (str): The answer or information found as a result of the research.
            parent (Optional[discord.Message], optional): A reference to the parent message to which this message should be linked. Defaults to None.

        Returns:
            Tuple[discord.Embed, discord.Message]: A tuple consisting of the constructed Embed object and the sent Discord message containing the research answer.
        '''
        query, question, comment = qatup
        embedres = discord.Embed(
            title=f"{quest}, depth: {self.depth}", description=answer
        )
        embedres.add_field(name="query", value=f"{query}"[:1000])
        embedres.set_footer(text=comment)

        this_message = await self.channel.send(embed=embedres, reference=parent)

        if parent and parent != self.res:
            par = await urltomessage(parent.jump_url, self.ctx.bot)

            embed = par.embeds[0]
            field = embed.fields[1]

            val = field.value
            val = val.replace(quest, f"[{quest}]({this_message.jump_url})")
            embed.set_field_at(1, name=field.name, value=val, inline=False)
            await par.edit(embed=embed)
        return embedres, this_message

    async def change_context(
        self,
        quest: str,
        answer: str,
        context: str,
        depth: int,
        this_message: discord.Message,
    ) -> str:
        
        context += f"{depth}:{quest}\n{answer}"
        self.answered.append(quest)
        new_depth = depth + 1
        return context, new_depth

    async def add_followups_to_stack(
        self,
        questions: List[str],
        followups: str,
        context: str,
        depth: int,
        this_message: discord.Message,
    ):
        """
        Asynchronously adds follow-up questions to the pending stack and update the
        current research's Message.

        Parameters:
        questions (List[str]): A list of follow-up questions to be added.
        followups (str): A string containing the follow-up questions concatenated together.
        context (str): The context in which the follow-up questions are being asked.
        depth (int): The recursion depth at which the follow-up questions were generated.
        this_message (discord.Message): The discord message object to be updated with follow-ups.

        Returns:
        str: The string of follow-up questions.
        """
        if questions:
            embedres = this_message.embeds[0]
            embedres.add_field(
                name="Followup questions", value=followups[:1020], inline=False
            )
            await this_message.edit(embed=embedres)

            for new_question in questions:
                self.add_to_stack(new_question, context, depth, this_message)
        return followups

    async def process_followups(
        self, context: str, new_depth: int, focus: str=""
    ) -> Tuple[List[str], str]:
        """
        Generates follow-up questions based on the provided context and the current depth.

        This method leverages a GPT model to dynamically generate follow-up questions that
        aim to expand upon the information provided in `context`. Questions similar to those
        already answered (`self.answered`) or currently being processed (`self.pending`) are
        excluded from generation to ensure a diverse range of enquiries.

        Parameters:
        - context: The combined context of prior questions and answers, formatted as a single string.
        - new_depth: The current depth in the follow-up question generation process.
        - this_message: The discord.Message object associated with the current question.

        Returns:
        - Tuple[List[str], str]: A tuple consisting of a list of follow-up questions and a string representation
          of these questions formatted for display purposes.
        """
        questions: List[str] = []
        followups: str = "None"
        donotask = [a for a in self.answered]
        donotask.extend(a for a in self.pending)
        if new_depth < self.depth:
            command: Optional[List[Any]] = None
            tries: int = 0
            while command is None and tries < 3:
                try:
                    lib = Followups()
                    sc = SingleCallAsync(
                        mylib=lib,
                        model="gpt-3.5-turbo-0125",
                        client=self.client,
                        timeout=30,
                    )
                    command = await sc.call_single(
                        f"Generate {self.followup} followup questions to expand on the "+\
                        f"results given the prior question/answer pairs \n{context}.  "+\
                        f"\nDo not generate a followup if it is similar to the questions answered here:{donotask}.\n"+\
                        f"{focus}",
                        "followupquestions",
                    )
                except Exception as e:
                    await self.ctx.send("Retrying...")
                    tries += 1
                    if tries >= 3:
                        raise e

            questions = command[0][1]["content"]

            followups = "\n".join(f"* {q}" for q in questions)

        return questions, followups

    def add_output_dict(
        self, quest: str, answer: str, links: List[str], depth: int, followups: str
    ) -> None:
        """Add a dictionary with the answer to a research query to the list.

        Args:
            quest (str): Question being answered
            answer (str): Answer generated by LLM.
            links (List[str]): Links used to generate answer.
            depth (int): The depth a question was asked at
            followups (str): Followup Questions.
        """
        result_dict = {
            "question": quest,
            "answer": answer,
            "sources": links,
            "depth": depth,
            "followups": followups,
        }
        self.results[quest] = result_dict

    async def send_file_results(self) -> None:
        """Send Files containing the results of the research operations back."""
        if self.search_web:
            file_buffer = StringIO()
            for line in self.alllines:
                file_buffer.write(f"{line}\n")
            file_buffer.seek(0)  # Go back to the start of the StringIO buffer
            await self.ctx.send(
                content="Websites",
                file=discord.File(file_buffer, filename="all_links.txt"),
            )
            file_buffer.close()  # Close the buffer
        file_buffer2 = StringIO()
        file_buffer2.write(f"{json.dumps(self.results, indent=2)}\n")
        file_buffer2.seek(0)  # Go back to the start of the StringIO buffer

        await self.ctx.send(
            content="File Results",
            file=discord.File(file_buffer2, filename="research.json"),
        )
        file_buffer2.close()  # Close the buffer

    async def single_iteration(
        self, current: Tuple[str, str, int, discord.Message]
    ) -> None:
        """
        1: Preform a web query (generate query, websearch, load_links),
        2: research a question using the collection, 
        3: Format the results and display, 
        4: add to the context
        5: generate followup questions
        6: add followup questions to the internal stack
        7: add output to the results dictionary.


        Args:
            current (Tuple[str, str, int, discord.Message]): _description_
        """
        quest, context, dep, parent = current
        self.pending.remove(quest)
        s1=f"<a:LoadingBlue:1206301904863502337>{len(self.answered)}/{self.all_runs}."+\
            f"stacklen={len(self.stack)} {quest},{dep}"
        await self.statmess.editw(
            min_seconds=5,
            content=s1,
        )
        qatup = ("No search.", quest, "Let's find out.")
        if self.search_web:
            qatup= await self.get_query_from_question(quest)
            links, details = await self.websearch(qatup)
            await self.load_links(qatup,links,details)

        answer, links, docs = await self.research(quest)
        emb, mess = await self.format_results(quest, qatup, answer, parent)

        newcontext, depth = await self.change_context(quest, answer, context, dep, mess)
        questions, followups = await self.process_followups(newcontext, depth)
        await self.add_followups_to_stack(questions,followups,newcontext,depth,mess)
        self.add_output_dict(quest, answer, links, dep, followups)
