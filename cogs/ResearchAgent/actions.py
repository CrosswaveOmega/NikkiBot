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
from .chromatools import ChromaTools
from .LinkLoader import SourceLinkLoader
from .tools import search_sim,get_doc_sources,format_answer
from langchain.docstore.document import Document
from utility import urltomessage,prioritized_string_split

async def research_op(
        question: str,
        k: int = 5,
        site_title_restriction: str = "None",
        use_mmr: bool = False,
        statmess:Optional[StatusEditMessage]=None,
        linkRestrict:List[str]=None
    ) -> Tuple[str, Optional[str],List[Document]]:
    """
    Search the chroma db for relevant documents pertaining to the
    question, and return a formatted result.

    Args:
        question (str): The question to be researched.
        k (int, optional): The number of results to return. Defaults to 5.
        site_title_restriction (str, optional): Restricts search results to a specific site if set. Defaults to "None".
        use_mmr (bool, optional): If set to True, uses Maximal Marginal Relevance for sorting results. Defaults to False.
        statmess (Optional[StatusEditMessage], optional): The status message object for updating search progress. Defaults to None.

    Returns:
        Tuple[str, Optional[str]]: A tuple containing the best answer to the question as a string,
                                    and an optional string of all sourced URLs if available.
    """


    chromac = ChromaTools.get_chroma_client()

    embed = discord.Embed(title=f"Query: {question} ")

    embed.add_field(name="Question", value=question, inline=False)

    # Search For Sources
    if statmess:
        await statmess.editw(
            min_seconds=0,
            embed=embed,
        )
    data = await search_sim(
        question,
        client=chromac,
        titleres=site_title_restriction,
        k=k,
        mmr=use_mmr,
    )

    if len(data) <= 0:
        return "NO RELEVANT DATA.", None, None

    # Sort documents by score
    docs2 = sorted(data, key=lambda x: x[1], reverse=False)
    # Get string containing most relevant source urls:
    url_desc, allsources = get_doc_sources(docs2)
    embed.description = f"Sources:\n{url_desc}"
    embed.add_field(
        name="Cache_Query",
        value=f"About {len(docs2)} entries where found.  Max score is {docs2[0][1]}",
    )
    if statmess:
        await statmess.editw(min_seconds=0, content="", embed=embed)
    answer = await format_answer(question, docs2)
    return answer, allsources, docs2