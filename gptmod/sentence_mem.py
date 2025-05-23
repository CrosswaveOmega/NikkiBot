"""
Functions for a lancedb based memory for the gptfunctions.
"""

import copy
import uuid
from typing import Any, Dict, List

import discord
from discord.ext import commands
from gptfunctionutil import AILibFunction, GPTFunctionLibrary, LibParamSpec
from langchain.docstore.document import Document


import threading
import gptmod.util as util
import gui

from utility.debug import Timer

DocumentScoreVector = None


class MemoryFunctions(GPTFunctionLibrary):
    @AILibFunction(
        name="add_to_memory",
        description="Based on the current chat context, update long-term memory with up to 20 sentences which can be used to remember the content.  Do not add sentences if they are already in the memory.",
    )
    @LibParamSpec(
        name="sentences",
        description="A list of 1 to 20 sentences which will be added to the long term memory.",
        minItems=1,
        maxItems=20,
    )
    @LibParamSpec(
        name="need_to_add",
        description="If the sentences are already present within the memory, set this to False.",
    )
    async def sentences(self, sentences: List[str], need_to_add: bool = True):
        # This is an example of a decorated coroutine command.
        return sentences, need_to_add


class GenericThread:
    def __init__(self, function):
        self.thread = None
        self.target = function
        self.result = None

    def run(self, *args, **kwargs):
        def wrapper(*args, **kwargs):
            self.result = self.target(*args, **kwargs)
            self.get_result()

        self.thread = threading.Thread(target=wrapper, args=args, kwargs=kwargs)
        self.thread.start()

    def get_result(self):
        if self.thread is None:
            return False
        if self.thread.is_alive():
            return False
        return self.result

    def __call__(self):
        return self.get_result()


gui.gprint("importing sentence_mem")


# Example target function
def warmup():
    gui.gprint("Starting embedding model.")
    with Timer() as timer:
        from langchain_huggingface import HuggingFaceEmbeddings

        hug_embed = HuggingFaceEmbeddings(model_name="thenlper/gte-small")
        hug_embed.embed_query("The quick brown fox jumped over the lazy frog.")
    gui.gprint("embedding model loaded in", timer.get_time())
    return hug_embed


def advanced_sentence_splitter(text):
    from nltk.tokenize import sent_tokenize

    sentences = sent_tokenize(text)
    return sentences


# symbol = re.escape("```")
# pattern = re.compile(f"({symbol}(?:(?!{symbol}).)+{symbol})", re.DOTALL)

# splitorder = [
#     pattern,
#     "\n# %s",
#     "\n## %s",
#     "\n### %s",
#     "\n#### %s",
#     "\n##### %s",
#     "\n###### %s",
#     "%s\n",
#     "%s.  ",
#     "%s. ",
#     "%s ",
# ]


def results_to_docs(results: Any) -> List[Document]:
    return [
        Document(page_content=result[0], metadata=result[1] or {})
        for result in zip(
            results["documents"],
            results["metadatas"],
        )
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


def split_document(doc: Document, present_mem=""):
    """
    Splits a Document object into smaller chunks based on sentences while maintaining

    Args:
        doc (Document): The Document object to be split.
        present_mem (str, optional): Additional memory context (default is "").

    Returns:
        List[Document]: A list of new Document objects with split content and updated
    """
    newdata = []
    metadata = doc.metadata
    add = 0
    fil = advanced_sentence_splitter(doc.page_content)

    for e, chunk in enumerate(fil):
        metadatac = copy.deepcopy(metadata)
        metadatac["split"] = add
        add += 1
        new_doc = Document(page_content=chunk, metadata=metadatac)
        if len(chunk) > 2:
            gui.gprint(chunk)
            newdata.append(new_doc)
        else:
            gui.gprint("skipping chunk due to insufficient size.")
    return newdata


async def group_documents(docs: List[Document], max_tokens=3000):
    sources: Dict[str : Dict[int, Any]] = {}
    context = ""
    for e, tup in enumerate(docs):
        doc = tup
        source, split = doc.metadata["source"], doc.metadata["split"]
        if source not in sources:
            sources[source] = {}
        sources[source][split] = doc
        if doc.page_content not in context:
            gui.gprint(doc.page_content)
            context += doc.page_content + "  "
        tokens = util.num_tokens_from_messages(
            [{"role": "system", "content": context}], "gpt-4o-mini"
        )
        if tokens >= max_tokens:
            gui.gprint("token break")
            break

    out_list = []
    for source, d in sources.items():
        newc = ""
        sorted_dict = sorted(d.items(), key=lambda x: x[0])
        lastkey = -6

        for k, v in sorted_dict:
            # gui.gprint(source, k, v)
            if k is not None and k != 0 and abs(k - lastkey) > 1:
                # gui.gprint(abs(k - lastkey))
                newc += "..."
            lastkey = k
            newc += f"[split:{k}]:{v.page_content}" + "  "
        if newc:
            meta = sorted_dict[0][1].metadata
            meta["splits"] = len(sorted_dict)
            doc = Document(page_content=newc.strip(), metadata=meta)
            out_list.append(doc)
    return out_list


def indent_string(input_string: str, spaces: int = 2):
    """
    Indents each line of the given string by a specified number of spaces.

    Args:
        inputString (str): The string to be indented.
        spaces (int, optional): Number of spaces to indent each line. Defaults to 2.

    Returns:
        str: The indented string.
    """
    indentation = " " * spaces
    indented_string = "\n".join(
        [indentation + line for line in input_string.split("\n")]
    )
    return indented_string


class SentenceMemory:
    def __init__(self, bot, guild, user):
        # dimensions = 384
        self.guildid = guild.id
        self.userid = user.id

        from gptmod.lancetools import LanceTools

        metadata = {"desc": "Simple long term memory.  384 dimensions."}
        self.coll = LanceTools.get_collection("sentence_mem", embed=bot.embedding())
        self.shortterm = {}

    async def get_neighbors(self, docs: List[Document]):
        """Retrieve all immediate neighbors of all docs in docs.
        Each neighbor of a doc has the same source attribute, as well as a split
        attribute that is one more or one less.

        Args:
            docs (List[Document]): List of documents

        Returns:
            List[Document]: All neighboring documents.
        """
        docs1 = []

        ids = set()
        for d in docs:
            source, split = d.metadata["source"], d.metadata["split"]
            ids.add(
                f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS, source))}],sid:[{split}]"
            )
            ids.add(
                f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS, source))}],sid:[{split - 1}]"
            )
            ids.add(
                f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS, source))}],sid:[{split + 1}]"
            )

        doc1 = await self.coll.aget_by_ids("sentence_mem", list(ids))
        return doc1
        gui.gprint(zip(doc1["documents"], doc1["metadatas"]))
        if doc1:
            dc = results_to_docs(doc1)
            if dc:
                docs1 = dc

        return docs1

    async def add_to_mem(
        self,
        ctx: commands.Context,
        message: discord.Message,
        cont=None,
        present_mem: str = "",
    ):
        content = cont
        if not content:
            content = message.content
        gui.gprint("content", content)
        meta = {}
        meta["source"] = message.jump_url
        meta["foruser"] = self.userid
        meta["forguild"] = self.guildid
        meta["channel"] = message.channel.id
        meta["date"] = message.created_at.timestamp()
        meta["role"] = "assistant"
        doc = Document(page_content=content, metadata=meta)
        docs = split_document(doc, present_mem)
        gui.gprint(docs)
        newdocs = []
        for e, doc in enumerate(docs):
            doc.id = f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS, doc.metadata['source']))}],sid:[{doc.metadata['split']}]"
            newdocs.append(doc)
        if docs:
            outs = self.coll.add_documents(newdocs)
            gui.gprint(outs)

    async def add_list_to_mem(
        self,
        ctx: commands.Context,
        message: discord.Message,
        cont: List[str],
        present_mem: str = "",
    ):
        content = cont
        gui.gprint("content", content)
        docs = []
        for e, c in enumerate(content):
            meta = {}
            meta["source"] = message.jump_url
            meta["foruser"] = self.userid
            meta["forguild"] = self.guildid
            meta["channel"] = message.channel.id
            meta["date"] = message.created_at.timestamp()
            meta["role"] = (
                "assistant" if message.author.id == ctx.bot.user.id else "user"
            )
            meta["split"] = e
            doc = Document(page_content=c, metadata=meta)
            doc.id = f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS, doc.metadata['source']))}],sid:[{doc.metadata['split']}]"

            docs.append(doc)

        if docs:
            self.coll.add_documents(docs)

    async def search_sim(self, message: discord.Message) -> List[DocumentScoreVector]:
        persist = "saveData"

        filterwith = f"foruser = {message.author.id} AND forguild = {message.guild.id};"

        sources: Dict[str : Dict[int, Any]] = {}
        with Timer() as all_timer:
            docs = await self.coll.asimilarity_search_with_relevance_scores(
                message.content, k=4, filter=filterwith
            )
            context = ""

            docs2 = (d[0] for d in docs)
            all_neighbors = await self.get_neighbors(docs2)

        checktime = all_timer.get_time()

        with Timer() as dict_timer:
            sources = await group_documents(all_neighbors)

        new_output = ""
        with Timer() as loadtimer:
            for source in sources:
                if source.page_content:
                    content = indent_string(source.page_content.strip(), 1)
                    output = f"*{content}\n"
                    new_output += output

        return docs, new_output, (all_timer, dict_timer, loadtimer)

    async def dump_memory(self, message: discord.Message) -> List[DocumentScoreVector]:
        persist = "saveData"

        filterwith = f"foruser = {message.author.id} AND forguild = {message.guild.id};"

        sources: Dict[str : Dict[int, Any]] = {}
        with Timer() as all_timer:
            docs = await self.coll.aget(filter=filterwith, limit=128)
            context = ""

            docs2 = results_to_docs(docs)
            gui.gprint(docs, docs2)
            all_neighbors = docs2

        checktime = all_timer.get_time()

        with Timer() as dict_timer:
            sources = await group_documents(all_neighbors)

        new_output = ""
        with Timer() as loadtimer:
            for source in sources:
                if source.page_content:
                    content = indent_string(source.page_content.strip(), 1)
                    output = f"*{content}\n"
                    new_output += output

        return docs, new_output, (all_timer, dict_timer, loadtimer)

    async def delete_message(self, url):
        try:
            self.coll.delete(filter=f'source="{url}"')

            return True
        except ValueError as e:
            gui.dprint(e)
            return False

    async def delete_user_messages(self, userid):
        try:
            self.coll.delete(filter=f"foruser={userid}")

            return True
        except ValueError as e:
            gui.dprint(e)
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
