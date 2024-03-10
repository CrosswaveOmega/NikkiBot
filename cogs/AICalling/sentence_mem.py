import asyncio
import copy
import datetime
import re
import uuid
from typing import Any, AsyncGenerator, List, Tuple, Union

from discord.ext import commands, tasks
import chromadb
import discord
import langchain_community.document_loaders as docload
import openai
from chromadb.types import Vector
from googleapiclient.discovery import build  # Import the library
from gptfunctionutil import AILibFunction, GPTFunctionLibrary, LibParam
from htmldate import find_date
from langchain.docstore.document import Document
from langchain.indexes import VectorstoreIndexCreator
from langchain_community.document_loaders import PDFMinerLoader, PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from tqdm.asyncio import tqdm_asyncio

import assets
import gptmod
import gui
from utility import chunk_list, prioritized_string_split
from utility.debug import Timer

from gptmod.chromatools import ChromaBetter as Chroma
from gptmod.chromatools import DocumentScoreVector, ChromaTools
from langchain_community.embeddings import HuggingFaceEmbeddings
from nltk.tokenize import sent_tokenize

hug_embed=HuggingFaceEmbeddings(model_name="thenlper/gte-small")

def advanced_sentence_splitter(text):
    sentences = sent_tokenize(text)
    return sentences


symbol = re.escape("```")
pattern = re.compile(f"({symbol}(?:(?!{symbol}).)+{symbol})")

splitorder = [
    pattern,
    "\n# %s",
    "\n## %s",
    "\n### %s",
    "\n#### %s",
    "\n##### %s",
    "\n###### %s",
    "%s\n",
    "%s.  ",
    "%s. ",
    "%s ",
]


async def try_until_ok(async_func, *args, **kwargs):
    """
    Attempts to run an asynchronous function up to  4 times.
    Example:
        completion = await try_until_ok(
                    asyncio.sleep(3),
                    timeout=60,
                )
    Args:
        async_func (Callable): The asynchronous function to run.
        *args: Positional arguments to pass to the asynchronous function.
        **kwargs: Keyword arguments to pass to the asynchronous function.

    Returns:
        Any: The result of the asynchronous function if it succeeds.

    Raises:
        Exception: If the asynchronous function fails after  4 attempts.
    """
    for tries in range(4):
        try:
            return await async_func(*args, **kwargs)
        except Exception as err:  # pylint: disable=broad-except
            if tries >= 3:
                raise err


def split_link(doc: Document,present_mem):
    newdata = []
    metadata = doc.metadata
    add = 0
    fil = advanced_sentence_splitter(doc.page_content)

    for e, chunk in enumerate(fil):
        metadatac = copy.deepcopy(metadata)
        metadatac["split"] = add
        add += 1
        new_doc = Document(page_content=chunk, metadata=metadatac)
        if len(chunk)>8:
            print(chunk)
            newdata.append(new_doc)
        else:
            print("skipping chunk")
    return newdata
def indent_string(inputString, spaces=2):
    indentation = " " * spaces
    indentedString = "\n".join(
        [indentation + line for line in inputString.split("\n")]
    )
    return indentedString

class SentenceMemory:
    def __init__(self, guild, user):
        #dimensions = 384
        self.guildid = guild.id
        self.userid = user.id
        metadata={
            'desc':'Simple long term memory.  384 dimensions.'
        }
        self.coll = ChromaTools.get_collection("sentence_mem",embed=hug_embed,path='saveData/longterm')
        self.shortterm={}

    async def get_neighbors(self, doc:Document):
        source,split=doc.metadata['source'], doc.metadata['split']
        print(source,split)
        ids = [
            f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS,source))}],sid:[{split-1}]",
            f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS,source))}],sid:[{split}]",
            f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS,source))}],sid:[{split+1}]",
        ]
        docs=self.coll.get(ids=ids)
        print(docs)
        return docs



    async def add_to_mem(
        self, ctx: commands.Context, message: discord.Message, cont=None, present_mem:str=""
    ):
        content = cont
        if not content:
            content = message.content
        print('content',content)
        meta = {}
        meta["source"] = message.jump_url
        meta["foruser"] = self.userid
        meta["forguild"] = self.guildid
        meta["channel"] = message.channel.id
        meta["date"] = message.created_at.timestamp()
        meta["role"] = "assistant" if message.author.id == ctx.bot.user.id else "user"
        doc = Document(page_content=content, metadata=meta)
        docs = split_link(doc,present_mem)
        ids = [
            f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS,doc.metadata['source']))}],sid:[{doc.metadata['split']}]"
            for e, doc in enumerate(docs)
        ]
        if docs:
            self.coll.add_documents(docs, ids)

    async def search_sim(self, message: discord.Message) -> List[DocumentScoreVector]:
        persist = "saveData"

        filterwith = {
            "$and": [
                {"foruser": message.author.id},
                {"forguild": message.guild.id},
            ]
        }
        docs = await self.coll.amax_marginal_relevance_search(
            message.content, k=15, filter=filterwith
        )
        context = ""
        
        for e, tup in enumerate(docs):
            doc = tup
            neighbors=await self.get_neighbors(doc)
            meta = doc.metadata
            source,split=doc.metadata['source'], doc.metadata['split']
            print("S",doc.page_content,"S",source,split)
            newc=""
            for n in neighbors['documents']:
                if n not in context:
                    newc+=n+"  "
            
            if newc:
                content=indent_string(newc.strip(),1)
                output = f"*{content}\n"
                context += output

            tokens = gptmod.util.num_tokens_from_messages(
                [{"role": "system", "content": context}], "gpt-3.5-turbo-0125"
            )

            if tokens >= 3000:
                print("token break")
                break
        print("MEMORY:")
        print(context)
        print("MEMORY OVER.")
        return docs, context

    async def delete_message(self, url):
        try:
            self.coll._collection.delete(where={"source": url})

            return True
        except ValueError as e:
            gui.dprint(e)
            return False

    async def delete_user_messages(self, userid):
        try:
            self.coll._collection.delete(where={"foruser": userid})

            return True
        except ValueError as e:
            gui.dprint(e)
            return False


def remove_url(
    url, collection="web_collection", client: chromadb.ClientAPI = None
) -> bool:
    persist = "saveData"
    if client != None:
        try:
            collectionvar = client.get_collection(collection)
            sres = collectionvar.peek()
            res = collectionvar.delete(where={"source": url})

            return True
        except ValueError as e:
            gui.dprint(e)
            raise e
            return False
    else:
        return False


def extract_embed_text(embed):
    """
    Extracts the text from an embed object and formats it as a bullet list.

    Args:
        embed (Embed): The embed object to extract text from.

    Returns:
        str: A string containing the title, description, and fields of the embed, formatted as a bullet list.
    """
    bullet_list = []

    # Extract title, description, and fields from the Embed
    if embed.title:
        bullet_list.append(f"{embed.title}")

    if embed.description:
        bullet_list.append(f"{embed.description}")

    for field in embed.fields:
        bullet_list.append(f"**{field.name}**: {field.value}")

    # Join the extracted text with bullet points
    bullet_string = "\n".join([f"• {line}" for line in bullet_list])
    return bullet_string
