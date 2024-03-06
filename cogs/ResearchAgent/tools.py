import discord
from gptfunctionutil import GPTFunctionLibrary, AILibFunction, LibParam
from utility import prioritized_string_split

from langchain_community.document_loaders import PyPDFLoader, PDFMinerLoader
from htmldate import find_date
import gptmod
from .ReadabilityLoader import ReadableLoader
from .chromatools import ChromaBetter as Chroma
from .chromatools import DocumentScoreVector
from langchain_openai import OpenAIEmbeddings
from langchain.indexes import VectorstoreIndexCreator
import asyncio
import copy
import datetime
from typing import Any, AsyncGenerator, List, Tuple
import chromadb
from googleapiclient.discovery import build  # Import the library

from chromadb.types import Vector
import assets
import re

import langchain_community.document_loaders as docload
import uuid
import openai
from langchain.docstore.document import Document
from .metadataenums import MetadataDocType
import gui

webload = docload.WebBaseLoader


tosplitby = [
    # First, try to split along Markdown headings (starting with level 2)
    "\n#{1,6} ",
    # Note the alternative syntax for headings (below) is not handled here
    # Heading level 2
    # ---------------
    # End of code block
    "```\n",
    # Horizontal lines
    "\n\\*\\*\\*+\n",
    "\n---+\n",
    "\n___+\n",
    " #{1,6} ",
    # Note that this splitter doesn't handle horizontal lines defined
    # by *three or more* of ***, ---, or ___, but this is not handled
    "\n\n",
    "\n",
    " ",
    "",
]
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


class MyLib(GPTFunctionLibrary):
    @AILibFunction(
        name="get_pdf_data",
        description="Return the title, authors, abstract, and date when given the first page of a PDF, if the info can be found.",
        enabled=True,
        force_words=["extract", "pdf"],
        required=["title"],
    )
    @LibParam(
        title="Title of the PDF given the first page.",
        authors="All authors of the PDF, given the first page.  If not available, pass in None",
        date="Date of publication of the PDF, in YYYY-MM-DD format.  You must return the Year, Month, and Day.  If it can't be found, return None.",
        abstract="Abstract found on the PDF.  If it can't be found, return not available.",
    )
    async def get_pdf_data(
        self,
        title: str,
        authors: str = "None",
        date: str = "None",
        abstract: str = "NA",
    ):
        # Wait for a set period of time.
        return title, authors, date, abstract


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


def google_search(bot, query: str, result_limit: int, kwargs: dict = {}) -> dict:
    query_service = build("customsearch", "v1", developerKey=bot.keys["google"])
    query_results = (
        query_service.cse()
        .list(q=query, cx=bot.keys["cse"], num=result_limit)  # Query  # CSE ID
        .execute()
    )
    print(query_results)
    return query_results


async def read_and_split_pdf(
    bot, url: str, chunk_size: int = 1800, chunk_overlap: int = 1
):
    mylib = MyLib()
    client = openai.AsyncClient()

    loader = PDFMinerLoader(url)
    data = await asyncio.wait_for(asyncio.to_thread(loader.load), timeout=25)
    completion = await client.chat.completions.create(
        model="gpt-3.5-turbo-0125",
        messages=[
            {
                "role": "system",
                "content": "Given the raw text of the first page of a pdf, execute the get_pdf_data data function.",
            },
            {
                "role": "user",
                "content": f"Please extract the data for this pdf: {(data[0].page_content)[:2000]}",
            },
        ],
        tools=mylib.get_tool_schema(),
        tool_choice="auto",
    )
    metadata = {}
    new_docs = []
    message = completion.choices[0].message
    if message.tool_calls:
        for tool in message.tool_calls:
            typev = int(MetadataDocType.pdftext)
            out = await mylib.call_by_tool_async(tool)
            title, authors, date, abstract = out["content"]
            metadata["authors"] = authors
            metadata["website"] = "PDF_ORIGIN"
            metadata["title"] = title
            metadata["source"] = url
            metadata["description"] = abstract
            metadata["language"] = "en"
            metadata["dateadded"] = datetime.datetime.utcnow().timestamp()
            metadata["sum"] = "source"
            metadata["type"] = typev
            metadata["date"] = date
            for e, pagedata in enumerate(data):
                newdata = copy.deepcopy(metadata)
                newdata["page"] = f"Page {e}"
                text = pagedata.page_content
                # dealing with awkward spacing
                filtered_text = re.sub(r"-\s*\n", "", text)
                filtered_text = re.sub(r" +", " ", filtered_text)
                doc = Document(page_content=filtered_text, metadata=newdata)

                new_docs.append(doc)
            return new_docs, typev
    else:
        raise Exception("ERROR:" + str(completion.choices[0].message.content))


async def read_and_split_link(
    bot, url: str, chunk_size: int = 1800, chunk_overlap: int = 1
) -> List[Document]:
    # Document loader
    prioritysplit = []
    if url.endswith(".pdf") or ".pdf?" in url:
        pdfmode = True
        symbol3 = re.escape("  ")
        pattern3 = re.compile(f"({symbol3}(?:(?!{symbol3}).)+{symbol3})")
        prioritysplit.append((pattern3, 100))
        data, typev = await read_and_split_pdf(bot, url, chunk_size)
    else:
        loader = ReadableLoader(
            url,
            header_template={
                "User-Agent": "Mozilla/5.0 (X11,Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
            },
        )
        # Index that wraps above steps
        data, typev = await loader.aload(bot)
    newdata = []
    splitnum = 0
    for d in data:
        # Strip excess white space.
        simplified_text = d.page_content.strip()
        simplified_text = re.sub(r"(\n){4,}", "\n\n\n", simplified_text)
        simplified_text = re.sub(r" {3,}", "  ", simplified_text)
        simplified_text = simplified_text.replace("\t{3,}", "\t")
        simplified_text = re.sub(r"\n+(\s*\n)*", "\n", simplified_text)
        d.page_content = simplified_text
        split, splitnum = await asyncio.to_thread(
            split_link, d, chunk_size=chunk_size, prior=prioritysplit, add=splitnum
        )
        newdata.extend(split)

    all_splits = newdata
    return all_splits, typev


def split_link(doc: Document, chunk_size: int = 1800, prior=[], add=0):
    newdata = []

    metadata = doc.metadata
    tosplitby = prior
    tosplitby.extend(splitorder)
    fil = prioritized_string_split(
        doc.page_content, tosplitby, default_max_len=chunk_size
    )

    for e, chunk in enumerate(fil):
        metadatac = copy.deepcopy(metadata)

        metadatac["split"] = add
        add += 1
        new_doc = Document(page_content=chunk, metadata=metadatac)
        newdata.append(new_doc)
    return newdata, add


async def add_summary(
    url: str,
    desc: str,
    header,
    collection="web_collection",
    client: chromadb.ClientAPI = None,
):
    # Index that wraps above steps
    persist = "saveData"
    newdata = []
    # data = await loader.aload()
    metadata = {}
    if header is not None:
        gui.dprint(header["byline"])
        if "byline" in header:
            metadata["authors"] = header["byline"]
        metadata["website"] = header.get("siteName", "siteunknown")
        metadata["title"] = header.get("title", "TitleError")
        metadata["source"] = url
        metadata["description"] = header.get("excerpt", "NA")
        metadata["language"] = header.get("lang", "en")
        metadata["dateadded"] = datetime.datetime.utcnow().timestamp()
        metadata["sum"] = "sum"
        metadata["split"] = "NA"
        metadata["type"] = int(MetadataDocType.readertext)
        metadata["date"] = "None"
        try:
            dt = find_date(url)
            if dt:
                metadata["date"] = dt
        except Exception as e:
            gui.dprint(e)
    newdata = {}
    for i, v in metadata.items():
        if v is not None:
            newdata[i] = v
    metadata = newdata
    docs = Document(page_content=desc, metadata=metadata)
    newdata = [docs]
    ids = [
        f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS,doc.metadata['source']))}],sum:[{e}]"
        for e, doc in enumerate(newdata)
    ]
    if client == None:
        vectorstore = Chroma.from_documents(
            documents=newdata,
            embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
            ids=ids,
            collection_name=collection,
            persist_directory=persist,
        )
        vectorstore.persist()
    else:
        vectorstore = Chroma.from_documents(
            documents=newdata,
            embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
            ids=ids,
            collection_name=collection,
            client=client,
            persist_directory=persist,
        )
        # vectorstore.persist()


def store_splits(
    splits, collection="web_collection", client: chromadb.ClientAPI = None
):
    persist = "saveData"
    ids = [
        f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS,doc.metadata['source']))}],sid:[{e+1}]"
        for e, doc in enumerate(splits)
    ]
    gui.dprint(splits)
    gui.dprint(ids)
    if client == None:
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
            ids=ids,
            collection_name=collection,
            persist_directory=persist,
        )
        vectorstore.persist()
    else:
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
            ids=ids,
            collection_name=collection,
            client=client,
            persist_directory=persist,
        )
        # vectorstore.persist()


def has_url(
    url, collection="web_collection", client: chromadb.ClientAPI = None
) -> bool:
    persist = "saveData"
    if client != None:
        try:
            collectionvar = client.get_collection(
                collection,
            )

            res = collectionvar.get(
                where={"source": url}, include=["documents", "metadatas"]
            )

            if res.get("ids", None):
                gui.dprint("hasres", res)
                return True, res
            return False, None
        except ValueError as e:
            gui.dprint(e)
            return False, None
    else:
        vs = Chroma(
            persist_directory=persist,
            embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
            collection_name=collection,
            client=client,
        )
        try:
            res = vs._collection.get(where={"source": url})
            gui.dprint(res)
            if res:
                return True
            else:
                return False
        except Exception as e:
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


async def search_sim(
    question: str,
    collection="web_collection",
    client: chromadb.ClientAPI = None,
    titleres="None",
    linkres=[],
    k=7,
    mmr=False,
) -> List[DocumentScoreVector]:
    persist = "saveData"
    vs = Chroma(
        client=client,
        persist_directory=persist,
        embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
        collection_name=collection,
    )
    filterwith = {}
    if titleres != "None":
        filterwith["title"] = {"$like": f"%{titleres}%"}
    if linkres:
        filterwith["source"] = {"$in": [linkres]}
    gui.dprint("here")
    if mmr:
        docs = vs.max_marginal_relevance_search(
            question,
            k=k,
            filter=filterwith,  # {'':titleres}}
        )
        docs = [(doc, 0.4) for doc in docs]
    else:
        docs = await vs.asimilarity_search_with_score_and_embedding(
            question, k=k, filter=filterwith  # {'':titleres}}
        )
    return docs


def get_doc_sources(docs: List[Tuple[Document, float]]):
    """
    Takes a list of Document objects, counts the appearances of unique sources amoung them,
    and return a string indicating the used sources.

    Args:
        docs (List[Tuple[Document,float]]): A list of tuples containing Document objects and their associated float score.

    Returns:
        str: A string formatted to list unique sources and the indices of their appearances in the provided list.
    """
    all_links = [doc.metadata.get("source", "???") for doc, e, i in docs]
    links = set(doc.metadata.get("source", "???") for doc, e, i, in docs)

    def ie(all_links: List[str], value: str) -> List[int]:
        return [index for index, link in enumerate(all_links) if link == value]

    used = "\n".join(f"{ie(all_links,l)}{l}" for l in links)
    source_pages = prioritized_string_split(used, ["%s\n"], 4000)
    cont = ""
    if len(source_pages) > 2:
        new = "\n"
        cont = f"...and {sum(len(se.split(new)) for se in source_pages[1:])} more."
    source_string = f"{source_pages[0]}{cont}"
    return source_string, used


async def debug_get(
    question: str,
    collection="web_collection",
    client: chromadb.ClientAPI = None,
    titleres="None",
    k=7,
) -> List[Tuple[Document, float]]:
    persist = "saveData"
    vs = Chroma(
        client=client,
        persist_directory=persist,
        embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
        collection_name=collection,
    )
    if titleres == "None":
        return "NONE"
    else:
        gui.dprint("here")

        collectionvar = client.get_collection(collection)
        res = collectionvar.get(
            where={"title": {"$like": f"%{titleres}%"}}, include=["metadatas"]
        )
        return res


async def get_points(
    question: str, docs: List[Tuple[Document, float, Vector]]
) -> AsyncGenerator[Tuple[Document, float, str, int], None]:
    """
    Extracts important bullet points from the provided sources to answer a given question.

    Args:
        question (str): The question to answer.
        docs (List[Tuple[Document, float]]): A list of tuples containing Document objects and their associated relevance scores.
        ctx (Optional[Context]): The context in which the function is called, if applicable.

    Returns:
        AsyncGenerator[Tuple[Document, float, str, int], None]: An asynchronous generator that yields tuples containing the Document object, its relevance score, the extracted bullet points, and the number of tokens used.

    Yields:
        Tuple[Document, float, str, int]: A tuple containing the Document object, its relevance score, the extracted bullet points, and the number of tokens used.
    """
    prompt = """
    Use the provided source to extract important bullet points
     to answer the question provided to you by the user.
    The sources will be in the system messages, slimmed down to a series of relevant snippits,
    in the following template:
        BEGIN
        **ID:** [Source ID number here]
        **Name:** [Name Here]
        **Link:** [Link Here]
        **Text:** [Text Content Here]
        END
    If a source appears to be unrelated to the question, note it.
    You responce must be in the following format:
    Concise Summary (3-7 sentences):
        Begin with a brief summary of the key points from the source snippet.
        Direct quotes are allowed if they enhance understanding.

    Detailed Response (5-10 bullet points):
     Expand on the summary by providing detailed information in bullet points.
     Ensure each bullet point captures essential details from the source, and be as descriptive as possible.
     The goal is not to summarize but to extract and convey relevant information,
      along with any context that could be important.
     Justify each bullet point by including 1-3 small direct snippits from the source, like this:
       * Bullet point with information.
        - 'the first snippit which justifies'
        - 'the second snippit that justifies the point'
       * The second bullet point with information.
        - 'the snippit which justifies point'
    Direct Quotes(3-4):
     Relevant, 1-5 sentence snippits from the original source which answer the question,
     If there is code in the source, you must place it here.
     

    """

    client = openai.AsyncOpenAI()
    for e, tup in enumerate(docs):
        doc, score, emb = tup
        tile = "NOTITLE" if "title" not in doc.metadata else doc.metadata["title"]
        output = f"""**ID**:{e}
        **Name:** {tile}
        **Link:** {doc.metadata['source']}
        **Text:** {doc.page_content}"""
        tokens = gptmod.util.num_tokens_from_messages(
            [{"role": "system", "content": output}], "gpt-3.5-turbo-0125"
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "system", "content": output},
            {"role": "user", "content": question},
        ]
        completion = None

        completion = await try_until_ok(
            client.chat.completions.create,
            model="gpt-3.5-turbo-0125",
            messages=messages,
            timeout=60,
        )

        doctup = (doc, score, completion.choices[0].message.content, tokens)

        yield doctup


async def format_answer(question: str, docs: List[Tuple[Document, float, Any]]) -> str:
    """
    Formats an answer to a given question using the provided documents.

    Args:
        question (str): The question to answer.
        docs (List[Tuple[Document, float]]): A list of tuples containing Document objects and relevance scores.

    Returns:
        str: The formatted answer as a string.
    """
    oldprompt = """
    Use the provided sources to answer question provided by the user.  
    Each of the sources will be in their own system messags, 
    slimmed down to a series of relevant snippits,
    and are in the following template:
        BEGIN
        **ID:** [Source ID number here]
        **Name:** [Name Here]
        **Link:** [Link Here]
        **Text:** [Text Content Here]
        END
    
    Your answer must be 3-7 medium-length paragraphs with 5-10 sentences per paragraph. 
    Preserve key information from the sources and maintain a descriptive tone. 
       
    Please include an inline citation with the source id for each website you retrieved data from in this format: [ID here].
    If there is no insufficient provided information from the sources, please state as such.
    Exclude any concluding remarks from the answer.

    """
    prompt = """

**Task:**
Use the provided sources, 
presented in individual system messages with relevant snippets, 
to craft a comprehensive response to the user's question. 
Each source is formatted in the following template:

```
BEGIN
**ID:** [Source ID number here]
**Name:** [Name Here]
**Link:** [Link Here]
**Text:** [Text Content Here]
END
```

**Guidelines:**
1. Your response should consist of 3-7 medium-length paragraphs, containing 5-10 sentences each.
2. Preserve crucial information from the sources and maintain a descriptive tone in your writing.
3. Ensure the inclusion of an inline citation for each piece of information obtained from a specific source,
   using this format: [ID here].
   **This is crucially important, as the inline citations are used to verify the response accuracy.**
4. If the sources do not provide sufficient information on a particular aspect of the question, explicitly state this limitation in your answer.
5. Omit any concluding remarks from your response.

    """
    # The websites may contradict each other, prioritize information from encyclopedia pages and wikis.
    # Valid news sources follow.
    # Your goal is not to summarize, your goal is to answer the user's question based on the provided sources.
    formatted_docs = []
    messages = [
        {"role": "system", "content": prompt},
    ]

    total_tokens = gptmod.util.num_tokens_from_messages(
        [{"role": "system", "content": prompt}, {"role": "user", "content": question}],
        "gpt-3.5-turbo-0125",
    )
    for e, tup in enumerate(docs):
        doc, _, emb = tup

        meta = doc.metadata
        content = doc.page_content
        tile = "NOTITLE"
        if "title" in meta:
            tile = meta["title"]
        output = f"""**ID**:{e}
        **Name:** {tile}
        **Link:** {meta['source']}
        **Text:** {content}"""
        formatted_docs.append(output)

        tokens = gptmod.util.num_tokens_from_messages(
            [{"role": "system", "content": output}], "gpt-3.5-turbo-0125"
        )

        if total_tokens + tokens >= 14000:
            print("token break")
            break
        total_tokens += tokens

        messages.append({"role": "system", "content": output})
        if total_tokens >= 14000:
            print("token break")
            break
    messages.append({"role": "user", "content": question})
    client = openai.AsyncOpenAI()
    for tries in range(0, 4):
        try:
            completion = await client.chat.completions.create(
                model="gpt-3.5-turbo-0125", messages=messages, timeout=60
            )
            return completion.choices[0].message.content
        except Exception as e:
            if tries >= 3:
                raise e


summary_prompt_old = """
    Summarize general news articles, forum posts, and wiki pages that have been converted into Markdown. 
    Condense the content into 2-5 medium-length paragraphs with 5-10 sentences per paragraph. 
    Preserve key information and maintain a descriptive tone.
    Exclude any concluding remarks.
"""

summary_prompt = """
    As a professional summarizer, create a concise and comprehensive summary of the provided text, 
    be it an article, post, conversation, or passage, while adhering to these guidelines:
    * Craft a summary that is detailed, thorough, in-depth, and complex, while maintaining clarity and conciseness.
    * Incorporate main ideas and essential information, eliminating extraneous language and focusing on critical aspects.
    * Rely strictly on the provided text, without including external information.
    * Format the summary into 2-5 medium-length paragraphs with 5-10 sentences per paragraph.
    * Large texts WILL be split up, but you will not be given the other parts of the text.

"""


async def summarize(prompt: str, article: str, mylinks: List[str]):
    client = openai.AsyncOpenAI()

    def local_length(st):
        return gptmod.util.num_tokens_from_messages(
            [
                {"role": "system", "content": summary_prompt + prompt},
                {"role": "user", "content": st},
            ],
            "gpt-3.5-turbo-0125",
        )

    result = ""
    fil = prioritized_string_split(article, splitorder, 10000, length=local_length)
    filelength = len(fil)
    for num, articlepart in enumerate(fil):
        print(num, filelength)
        messages = [
            {
                "role": "system",
                "content": f"{summary_prompt}\n{prompt}\n You are viewing part {num+1}/{filelength} ",
            },
            {"role": "user", "content": f"\n {articlepart}"},
        ]
        completion = await try_until_ok(
            client.chat.completions.create,
            model="gpt-3.5-turbo-0125",
            messages=messages,
            timeout=60,
        )

        result = completion.choices[0].message.content
        for link in mylinks:
            link_text, url2 = link
            link_text = link_text.replace("_", "")
            gui.dprint(link_text, url2)
            if link_text in result:
                gui.dprint(link_text, url2)
                # sources.append(f"[{link_text}]({url})")
                result = result.replace(link_text, f"{link_text}")
        yield result


async def list_sources(
    ctx: discord.ext.commands.Context, title: str, sources: List[str]
) -> None:
    """
    Sends an embed to the context with a list of sources for a given title, split into multiple messages if necessary.

    Args:
        ctx (discord.ext.commands.Context): The context of where to send the embed.
        title (str): The title for the embed.
        sources (List[str]): A list of source URLs to include in the embed.
    """

    if len(sources) > 20:
        return
    embed = discord.Embed(title=f"Sources for {title}")
    sause = ""
    for i, source in enumerate(
        prioritized_string_split("\n".join(sources), ["%s\n"], 1020)
    ):
        embed.add_field(name=f"Sources Located: {i}", value=source, inline=False)
        sause += source
        if (i + 1) % 6 == 0 or i == len(sources) - 1:
            await ctx.send(embed=embed)
            embed, sause = discord.Embed(title=f"Sources for {title}"), ""
    if sause:
        await ctx.send(embed=embed)


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
