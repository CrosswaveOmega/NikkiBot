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
from .chromatools import ChromaTools, DocumentScoreVector
from .LinkLoader import SourceLinkLoader
from .tools import search_sim,get_doc_sources,format_answer
from langchain.docstore.document import Document
from utility import urltomessage,prioritized_string_split
from openai import AsyncClient
import chromadb
from chromadb.types import Vector
from nltk.tokenize import sent_tokenize
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

def advanced_sentence_splitter(text):
    sentences = sent_tokenize(text)
    return sentences
    
def split_sentences(text: str) -> List[str]:
    return re.split(r'(?<=[.!?]) +', text)

def get_closest(sentemb: List[float], docs: List[Tuple[Document, float, List[float]]]) -> List[Tuple[int,float]]:
    """
    Find the documents closest to a given sentence embedding within a list of documents.

    Args:
        sentemb: The embedding of the sentence as a list of floats.
        docs: A list of tuples, each containing a document, unspecified data, and the document's embedding.

    Returns:
        A tuple of two lists: the first list contains the top 4 closest documents,
        and the second list contains their corresponding similarity scores.
    """
    sentemb_array = np.array(sentemb)
    sentemb_array = sentemb_array.reshape(1, -1)
    top_docs = []  # Initialize with empty list to collect top similar documents
    similarity_scores = []  # Initialize with empty list to collect similarity scores

    for id, doc in enumerate(docs):
        doc,_,emb=doc

        # Assuming emb and sentemb are lists containing embeddings
        emb_array = np.array(emb)

        # Reshaping to 2D arrays for cosine similarity comparison
        emb_array = emb_array.reshape(1, -1)


        # Compute cosine similarity
        similarity_score = cosine_similarity(emb_array, sentemb_array)

        # Collect all similarity scores and corresponding documents
        similarity_scores.append(similarity_score[0])
        top_docs.append((id, similarity_score[0]))

    
    top_docs = sorted(top_docs, key=lambda x: x[1], reverse=True)

    # Extracting documents and their scores into separate lists
    return top_docs
        
def chunk_sentences(sentences: List[str], chunk_size: int = 10) -> List[List[str]]:
    '''Chunk sentences into blocks of 10.'''
    return [sentences[i:i + chunk_size] for i in range(0, len(sentences), chunk_size)]

async def sentence_sim_op(answer: str, docs: List[DocumentScoreVector]) -> List[Tuple[int, str, List[int], float, float]]:
    '''EXPERIMENTAL.  Evaluate how well each sentence matches with the sources.'''
    client = AsyncClient()

    sentences = advanced_sentence_splitter(answer)
    sentence_length = len(sentences)
    chunks = chunk_sentences(sentences)

    id = 0
    result = []
    for chunk in chunks:
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=chunk,
            encoding_format="float",
            timeout=25
            )
        for sent, c in zip(chunk, resp.data):
            sentemb = c.embedding
            top_docs: List[Tuple[int, float]] = await asyncio.to_thread(get_closest, sentemb, docs)

            filtered_docs = [doc for doc in top_docs if doc[1] > 0.05]
            sorted_docs = sorted(filtered_docs, key=lambda x: x[1], reverse=True)

            sorted_docs = sorted_docs[:4]

            #out=(id, sentence_id, list of val0 in sorted_docs, average val1 score, max val1 score.)
            val=[doc[1] for doc in sorted_docs]
            mean=round(float(np.mean(val))*100,1)
            maxv=round(float(max(val))*100,1)
            out = (id, sent, [doc[0] for doc in sorted_docs], mean, maxv)
            result.append(out)
            id += 1

    return result

async def research_op(
        question: str,
        k: int = 5,
        site_title_restriction: str = "None",
        use_mmr: bool = False,
        statmess:Optional[StatusEditMessage]=None,
        linkRestrict:List[str]=None
    ) -> Tuple[str, Optional[str],List[DocumentScoreVector]]:
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
