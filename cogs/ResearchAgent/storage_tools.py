import asyncio

import datetime
import uuid
from typing import List, Tuple

import lancedb
from htmldate import find_date
from langchain.docstore.document import Document
from langchain_openai import OpenAIEmbeddings
from tqdm.asyncio import tqdm_asyncio

import gui
from utility import chunk_list

from gptmod.lancetools import LanceTools, LanceBetter, DocumentScoreVector
from gptmod.metadataenums import MetadataDocType


async def add_summary(
    url: str,
    desc: str,
    header,
    collection="web_collection",
    client: lancedb.LanceDBConnection = None,
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
    docs.id = (
        f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS, docs.metadata['source']))}],sum:[0]"
    )
    usethesedocs = [docs]
    if client == None:
        client = LanceTools.get_lance_client()
        vectorstore = LanceTools.configure_lance_client(
            embed=OpenAIEmbeddings(model="text-embedding-3-small"),
            collection=collection,
            client=client,
        )
        await vectorstore.aadd_documents(usethesedocs)
    else:
        vectorstore = LanceTools.configure_lance_client(
            embed=OpenAIEmbeddings(model="text-embedding-3-small"),
            collection=collection,
            client=client,
        )
        await vectorstore.aadd_documents(usethesedocs)
        # vectorstore.persist()


async def store_many_splits(
    splits: List[Document],
    collection="web_collection",
    client: lancedb.LanceDBConnection = None,
):
    """
    Generate unique ids for each split, and then
    load them into LanceDB

    Parameters:
    - splits (List[Document]): A list of Document objects to be stored.
    - collection (str, optional): The name of the collection where documents will be stored.
      Defaults to "web_collection".
    - client (lancedb.LanceDBConnection, optional): An instance of a lancedb.LanceDBConnection. If not provided,
      the function will store the documents locally. Defaults to None.

    Returns:
    - None: The function performs storage operations but returns no value.
    """
    chunk_size = 10
    for e, doc in enumerate(splits):
        doc.id = f"url:[{str(uuid.uuid5(uuid.NAMESPACE_DNS, doc.metadata['source']))}],sid:[{doc.metadata['split']}]"

    chunked2 = chunk_list(splits, chunk_size)
    tasks = []
    client = LanceTools.get_lance_client()
    vs = LanceTools.configure_lance_client(
        client=client,
        embed=OpenAIEmbeddings(model="text-embedding-3-small"),
        collection=collection,
    )

    for s in chunked2:
        storeval = asyncio.to_thread(store_splits, s, vs)
        task = asyncio.ensure_future(storeval)
        tasks.append(task)

    return await tqdm_asyncio.gather(*tasks, desc="saving", ascii=True, mininterval=1)


def store_splits(splits: List[Document], lance: LanceBetter):
    """
    This function embeds the splits within splits and ids within the lance client.

    Parameters:
    - splits (List[Document]): A list of Document objects to be stored.

    Returns:
    - None: The function performs storage operations but returns no value.
    """
    persist = "saveData"
    lance.add_documents(splits)

    # vectorstore.persist()


def has_url(
    url, collection="web_collection", client: lancedb.LanceDBConnection = None
) -> bool:
    persist = "saveData"
    if client != None:
        try:
            table = client.open_table(
                collection,
            )
            res = table.search().where(f'source="{url}"').to_list()
            if res:
                return True, res
            return False, None
        except ValueError as e:
            gui.dprint(e)
            return False, None
    else:
        raise Exception("SET A CONNECTION.")


async def debug_get(
    question: str,
    collection="web_collection",
    client: lancedb.LanceDBConnection = None,
    titleres="None",
    k=7,
) -> List[Tuple[Document, float]]:
    persist = "saveData"
    vs = LanceTools.configure_lance_client(
        client=client,
        embed=OpenAIEmbeddings(model="text-embedding-3-small"),
        collection=collection,
    )
    if titleres == "None":
        return "NONE"
    else:
        gui.dprint("here")
        res = vs.get(f"title LIKE '%{titleres}%'", 10)
        return res


def remove_url(
    url, collection="web_collection", client: lancedb.LanceDBConnection = None
) -> bool:
    persist = "saveData"
    if client != None:
        try:
            table = client.open_table(
                collection,
            )
            res = table.delete(f'source="{url}"')
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
    client: lancedb.LanceDBConnection = None,
    titleres="None",
    linkres=[],
    k=7,
    mmr=False,
) -> List[DocumentScoreVector]:
    vs = LanceTools.configure_lance_client(
        client=client,
        embed=OpenAIEmbeddings(model="text-embedding-3-small"),
        collection=collection,
    )
    filterwith = ""
    if titleres != "None":
        titleres = f"title LIKE '%{titleres}%'"
        filterwith=titleres

    gui.dprint("here")
    if mmr:
        docs = vs.max_marginal_relevance_search(
            question,
            k=k,
            filter=filterwith,  # {'':titleres}}
        )
    else:
        docs = await vs.asimilarity_search_with_relevance_scores(
            question,
            k=k,
            filter=filterwith,  # {'':titleres}}
        )
    return docs
