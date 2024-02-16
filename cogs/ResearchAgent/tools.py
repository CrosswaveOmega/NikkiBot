import discord
from gptfunctionutil import GPTFunctionLibrary, AILibFunction, LibParam
from utility import prioritized_string_split
from langchain_community.document_loaders import PyPDFLoader, PDFMinerLoader
from htmldate import find_date
import gptmod
from .ReadabilityLoader import ReadableLoader
from langchain.vectorstores.chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.indexes import VectorstoreIndexCreator
import asyncio
import copy
import datetime
from typing import List, Tuple
import chromadb
from googleapiclient.discovery import build  # Import the library

import assets
import re

import langchain_community.document_loaders as docload
import uuid
import openai
from langchain.docstore.document import Document
from .metadataenums import MetadataDocType
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


def google_search(bot, query: str, result_limit: int):
    query_service = build("customsearch", "v1", developerKey=bot.keys["google"])
    query_results = (
        query_service.cse()
        .list(q=query, cx=bot.keys["cse"], num=result_limit)  # Query  # CSE ID
        .execute()
    )
    results = query_results["items"]
    return results


async def read_and_split_pdf(
    bot, url: str, chunk_size: int = 1800, chunk_overlap: int = 1
):
    mylib = MyLib()
    client = openai.AsyncClient()
    loader = PDFMinerLoader(url)
    data = loader.load()
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
            typev=int(MetadataDocType.pdftext)
            out=await mylib.call_by_tool_async(tool)
            title, authors, date, abstract = out['content']
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
            return new_docs,typev
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
        data, typev= await read_and_split_pdf(bot, url, chunk_size)
    else:
        loader = ReadableLoader(
            url,
            header_template={
                "User-Agent": "Mozilla/5.0 (X11,Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
            },
        )
        # Index that wraps above steps
        data, typev = await loader.aload(bot)
    print("ok")
    newdata = []
    splitnum=0
    for d in data:
        # Strip excess white space.
        simplified_text = d.page_content.strip()
        simplified_text = re.sub(r"(\n){4,}", "\n\n\n", simplified_text)
        simplified_text = re.sub(r" {3,}", "  ", simplified_text)
        simplified_text = simplified_text.replace("\t{3,}", "\t")
        simplified_text = re.sub(r"\n+(\s*\n)*", "\n", simplified_text)
        d.page_content = simplified_text
        split,splitnum = await split_link(d, chunk_size=chunk_size, prior=prioritysplit,add=splitnum)
        newdata.extend(split)

    all_splits = newdata
    return all_splits,typev


async def split_link(doc: Document, chunk_size: int = 1800, prior=[],add=0):
    newdata = []

    metadata = doc.metadata
    tosplitby = prior
    tosplitby.extend(splitorder)
    fil = prioritized_string_split(
        doc.page_content, tosplitby, default_max_len=chunk_size
    )

    for e, chunk in enumerate(fil):
        metadatac = copy.deepcopy(metadata)
        
        metadatac['split']=add
        add+=1
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
        print(header["byline"])
        if "byline" in header:
            metadata["authors"] = header["byline"]
        metadata["website"] = header.get("siteName", "siteunknown")
        metadata["title"] = header.get("title", "TitleError")
        metadata["source"] = url
        metadata["description"] = header.get("excerpt", "NA")
        metadata["language"] = header.get("lang", "en")
        metadata["dateadded"] = datetime.datetime.utcnow().timestamp()
        metadata["sum"] = "sum"
        metadata["split"]="NA"
        metadata["type"] = int(MetadataDocType.readertext)
        metadata["date"] = "None"
        try:
            dt = find_date(url)
            if dt:
                metadata["date"] = dt
        except Exception as e:
            print(e)
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
            embedding=OpenAIEmbeddings(),
            ids=ids,
            collection_name=collection,
            persist_directory=persist,
        )
        vectorstore.persist()
    else:
        vectorstore = Chroma.from_documents(
            documents=newdata,
            embedding=OpenAIEmbeddings(),
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
    print(splits)
    print(ids)
    if client == None:
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=OpenAIEmbeddings(),
            ids=ids,
            collection_name=collection,
            persist_directory=persist,
        )
        vectorstore.persist()
    else:
        vectorstore = Chroma.from_documents(
            documents=splits,
            embedding=OpenAIEmbeddings(),
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
            collectionvar = client.get_collection(collection)
            sres = collectionvar.peek()
            res = collectionvar.get(
                where={"source": url}, include=["documents", "metadatas"]
            )

            if res.get("ids", None):
                print("hasres", res)
                return True, res
            return False, None
        except ValueError as e:
            print(e)
            raise e
            return False
    else:
        vs = Chroma(
            persist_directory=persist,
            embedding_function=OpenAIEmbeddings(),
            collection_name=collection,
            client=client,
        )
        try:
            res = vs._collection.get(where={"source": url})
            print(res)
            if res:
                return True
            else:
                return False
        except Exception as e:
            print(e)
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
            print(e)
            raise e
            return False
    else:
        return False


async def search_sim(
    question: str,
    collection="web_collection",
    client: chromadb.ClientAPI = None,
    titleres="None",
    k=7,
    mmr=False,
) -> List[Tuple[Document, float]]:
    persist = "saveData"
    vs = Chroma(
        client=client,
        persist_directory=persist,
        embedding_function=OpenAIEmbeddings(),
        collection_name=collection,
    )
    if titleres == "None":
        if mmr:
            docs = vs.max_marginal_relevance_search(question, k=k)
            docs = [(doc, 0.4) for doc in docs]
        else:
            docs = await vs.asimilarity_search_with_relevance_scores(question, k=k)

        return docs
    else:
        print("here")
        if mmr:
            docs = vs.max_marginal_relevance_search(
                question,
                k=k,
                filter={"title": {"$like": f"%{titleres}%"}},  # {'':titleres}}
            )
            docs = [(doc, 0.4) for doc in docs]
        else:
            docs = await vs.asimilarity_search_with_relevance_scores(
                question,
                k=k,
                filter={"title": {"$like": f"%{titleres}%"}},  # {'':titleres}}
            )
        return docs


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
        embedding_function=OpenAIEmbeddings(),
        collection_name=collection,
    )
    if titleres == "None":
        return "NONE"
    else:
        print("here")

        collectionvar = client.get_collection(collection)
        res = collectionvar.get(
            where={"title": {"$like": f"%{titleres}%"}}, include=["metadatas"]
        )
        return res

async def get_points(question:str,docs:List[Tuple[Document, float]],ctx=None)->str:
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
    Concise Summary (2-4 sentences):
        Begin with a brief summary of the key points from the source snippet. 
        Direct quotes are allowed if they enhance understanding.

    Detailed Response (5-10 bullet points):
     Expand on the summary by providing detailed information in bullet points. 
     Ensure each bullet point captures essential details from the source, and be as descriptive as possible. 
     The goal is not to summarize but to extract and convey relevant information.
    
    """
    
    client = openai.AsyncOpenAI()
    formatted_docs = []
    lastv=[]
    for e, tup in enumerate(docs):
        doc, score = tup
        # print(doc)
        # 'metadata',{'title':'UNKNOWN','source':'unknown'})
        meta = doc.metadata
        content = doc.page_content  # ('page_content','Data lost!')
        tile = "NOTITLE"
        if "title" in meta:
            tile = meta["title"]
        output = f"""**ID**:{e}
        **Name:** {tile}
        **Link:** {meta['source']}
        **Text:** {content}"""
        formatted_docs.append(output)
        # print(output)
        tokens = gptmod.util.num_tokens_from_messages(
            [{"role": "system", "content": output}], "gpt-3.5-turbo-0125"
        )
        


        messages=[]
        messages = [
        {"role": "system", "content": prompt},
        ]
        messages.append({"role": "system", "content": output})

        messages.append({"role": "user", "content": question})
        
        completion = await client.chat.completions.create(
            model="gpt-3.5-turbo-0125", messages=messages
        )
        docs=(doc,completion.choices[0].message.content)
        if ctx:
            d,c=docs
            emb=discord.Embed(title=d.metadata.get("title","?"), description=c)
            emb.add_field(name="source",value=meta['source'],inline=False)
            emb.add_field(name="score",value="{:.4f}".format(score*100.0))
            emb.add_field(name="split value",value=f"{meta.get('split','?')}")
            emb.add_field(name="source_tokens",value=f"{tokens}")
            await ctx.send(embed=emb)

        lastv.append(docs)
    return lastv 

async def format_answer(question: str, docs: List[Tuple[Document, float]]) -> str:
    """
    Formats an answer to a given question using the provided documents.

    Args:
        question (str): The question to answer.
        docs (List[Tuple[Document, float]]): A list of tuples containing Document objects and relevance scores.

    Returns:
        str: The formatted answer as a string.
    """
    prompt = """
    Use the provided sources to answer question provided to you by the user.  Each of your source web pages will be in their own system messags, slimmed down to a series of relevant snippits,
    and are in the following template:
        BEGIN
        **ID:** [Source ID number here]
        **Name:** [Name Here]
        **Link:** [Link Here]
        **Text:** [Text Content Here]
        END
    The websites may contradict each other, prioritize information from encyclopedia pages and wikis.  Valid news sources follow.  
    Your answer must be 3-7 medium-length paragraphs with 5-10 sentences per paragraph. 
    Preserve key information from the sources and maintain a descriptive tone. 
    Your goal is not to summarize, your goal is to answer the user's question based on the provided sources.  
    Please include an inline citation with the source id for each website you retrieved data from in this format: [ID here].
    If there is no information related to the user's question, simply state that you could not find an answer and leave it at that. 
    Exclude any concluding remarks from the answer.

    """
    formatted_docs = []
    messages = [
        {"role": "system", "content": prompt},
    ]

    total_tokens = gptmod.util.num_tokens_from_messages(
        [{"role": "system", "content": prompt}, {"role": "user", "content": question}],
        "gpt-3.5-turbo-0125",
    )
    for e, tup in enumerate(docs):
        doc, score = tup
        # print(doc)
        # 'metadata',{'title':'UNKNOWN','source':'unknown'})
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
        # print(output)
        tokens = gptmod.util.num_tokens_from_messages(
            [{"role": "system", "content": output}], "gpt-3.5-turbo-0125"
        )

        if total_tokens + tokens >= 14000:
            break
        total_tokens += tokens

        messages.append({"role": "system", "content": output})
        if total_tokens >= 12000:
            break
    messages.append({"role": "user", "content": question})
    client = openai.AsyncOpenAI()
    completion = await client.chat.completions.create(
        model="gpt-3.5-turbo-0125", messages=messages
    )
    return completion.choices[0].message.content


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
