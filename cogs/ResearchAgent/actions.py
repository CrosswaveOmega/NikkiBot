import asyncio

# import datetime
from collections import defaultdict
from typing import List, Optional, Tuple

import discord
import numpy as np
from nltk.tokenize import sent_tokenize
from openai import AsyncClient
from sklearn.metrics.pairwise import cosine_similarity

from bot import StatusEditMessage

from gptmod.chromatools import ChromaTools, DocumentScoreVector
from .tools import format_answer, get_doc_sources, search_sim, try_until_ok

UPPER_VALIDATION_LIM = 5


def advanced_sentence_splitter(text):
    sentences = sent_tokenize(text)
    return sentences


def get_closest(
    sentemb: List[float], docs: List[DocumentScoreVector]
) -> List[Tuple[int, float]]:
    """
    Find the documents closest to a given sentence embedding within a list of documents.

    Args:
        sentemb: The embedding of the sentence as a list of floats.
        docs: A list of tuples, each containing a document, unspecified data, and the document's embedding.

    Returns:
        a sorted list of tuples: the first value contains the id of each close source
        and the second value contains their corresponding similarity scores.
    """
    sentemb_array = np.array(sentemb)
    sentemb_array = sentemb_array.reshape(1, -1)
    top_docs = []  # Initialize with empty list to collect top similar documents
    similarity_scores = []  # Initialize with empty list to collect similarity scores

    for docid, doc in enumerate(docs):
        doc, _, emb = doc

        # Assuming emb and sentemb are lists containing embeddings
        emb_array = np.array(emb)

        # Reshaping to 2D arrays for cosine similarity comparison
        emb_array = emb_array.reshape(1, -1)

        # Compute cosine similarity
        similarity_score = cosine_similarity(emb_array, sentemb_array)

        # Collect all similarity scores and corresponding documents
        similarity_scores.append(similarity_score[0][0])
        top_docs.append((docid, similarity_score[0][0]))

    top_docs = sorted(top_docs, key=lambda x: x[1], reverse=True)

    # Extracting documents and their scores into separate lists
    return top_docs


def chunk_sentences(sentences: List[str], chunk_size: int = 10) -> List[List[str]]:
    """Chunk sentences into blocks of 10."""
    return [sentences[i : i + chunk_size] for i in range(0, len(sentences), chunk_size)]


SentenceRes = List[Tuple[int, str, List[int], float, float]]


async def sentence_sim_op(
    answer: str, docs: List[DocumentScoreVector]
) -> Tuple[SentenceRes, List[Tuple[int, float, float]], float]:
    """Evaluate how well each sentence in an answer matches with sources.

    This method calculates and returns the similarity scores between the sentences in an answer
    and a list of document embeddings provided. It performs this calculation for each sentence,
    chunking the sentences for efficiency, and returns a comprehensive list of matches,
    along with averaged and maximum similarity scores for each source document.

    Args:
        answer (str): The answer containing sentences to be scored.
        docs (List[DocumentScoreVector]): A list of DocumentScoreVector,
        representing each document's metadata and embeddings.

    Returns:
        Tuple of a list of matches per sentence, list of averaged and maximum similarity
        scores per document,
        and the overall mean similarity score across all documents.
    """
    client = AsyncClient()

    sentences = advanced_sentence_splitter(answer)
    sentence_length = len(sentences)
    chunks = chunk_sentences(sentences, 25)
    all_distances = []
    sent_id = 0
    result = []
    doc_map = defaultdict(list)
    for chunk in chunks:
        resp = await try_until_ok(
            client.embeddings.create,
            model="text-embedding-3-small",
            input=chunk,
            encoding_format="float",
            timeout=25,
        )
        for sent, c in zip(chunk, resp.data):
            top_docs: List[Tuple[int, float]] = await asyncio.to_thread(
                get_closest, c.embedding, docs
            )

            filtered_docs = [doc for doc in top_docs if doc[1] > 0.05]

            # Add to map.

            sorted_docs = sorted(filtered_docs, key=lambda x: x[1], reverse=True)
            all_distances.extend([distance for _, distance in sorted_docs])
            for i, score in filtered_docs:
                doc_map[i].append((i, score))
            # get first 4 entries (the closest matches, and return the ids, mean, and max)
            sorted_docs = sorted_docs[:4]

            val = [doc[1] for doc in sorted_docs]
            out = (
                sent_id,
                sent,
                [doc[0] for doc in sorted_docs],
                round(float(np.mean(val)) * 100, 1),
                round(float(max(val)) * 100, 1),
            )
            result.append(out)
            sent_id += 1

    # Get averages and max for each source separately
    averages_and_maxes = [
        (
            id,
            np.mean([score for _, score in sublist]),
            np.max([score for _, score in sublist]),
        )
        for id, sublist in doc_map.items()
    ]
    mean_similarity = 1 - np.mean(all_distances)
    averages_and_maxes = sorted(averages_and_maxes, key=lambda x: x[0])
    return result, averages_and_maxes, mean_similarity


async def research_op(
    question: str,
    k: int = 5,
    site_title_restriction: str = "None",
    use_mmr: bool = False,
    statmess: Optional[StatusEditMessage] = None,
    link_restrict: Optional[List[str]] = None,
) -> Tuple[str, Optional[str], List[DocumentScoreVector]]:
    """
    Search the chroma db for relevant documents pertaining to the
    question, and return a formatted result with the source links and original documents.

    Args:
        question (str): The question to be researched.
        k (int, optional): The number of results to return. Defaults to 5.
        site_title_restriction (str, optional):
            Restricts search results to a specific site if set. Defaults to "None".
        use_mmr (bool, optional):
            If set to True, uses Maximal Marginal Relevance for sorting results.
              Defaults to False.
        statmess (StatusEditMessage, optional):
            The status message object for updating search progress. Defaults to None.
        link_restrict (List[str],optional): Restrict database search to these links.

    Returns:
        Tuple[str, Optional[str], List[DocumentScoreVector]]:
            A tuple comprising the best answer, an optional string containing
            URLs of all sources, and a list of DocumentScoreVector objects for the top documents.

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
        linkres=link_restrict,
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


async def get_sources(
    question: str,
    k: int = 5,
    site_title_restriction: str = "None",
    use_mmr: bool = False,
    statmess: Optional[StatusEditMessage] = None,
    link_restrict: Optional[List[str]] = None,
) -> Tuple[str, Optional[str], List[DocumentScoreVector]]:
    """
    Search the chroma db for relevant documents pertaining to the
    question, and return a formatted result with the source links and original documents.

    Args:
        question (str): The question to be researched.
        k (int, optional): The number of results to return. Defaults to 5.
        site_title_restriction (str, optional):
            Restricts search results to a specific site if set. Defaults to "None".
        use_mmr (bool, optional):
            If set to True, uses Maximal Marginal Relevance for sorting results.
              Defaults to False.
        statmess (StatusEditMessage, optional):
            The status message object for updating search progress. Defaults to None.
        link_restrict (List[str],optional): Restrict database search to these links.

    Returns:
        Tuple[str, Optional[str], List[DocumentScoreVector]]:
            A tuple comprising the best answer, an optional string containing
            URLs of all sources, and a list of DocumentScoreVector objects for the top documents.

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
        linkres=link_restrict,
    )

    if len(data) <= 0:
        return "NO RELEVANT DATA.", None, None

    # Sort documents by score
    docs2 = sorted(data, key=lambda x: x[0].metadata["split"], reverse=False)
    docs3 = {}
    for doc in docs2:
        source = doc[0].metadata["source"]
        if not source in docs3:
            docs3[source] = []
        docs3[source].append(doc)

    # Get string containing most relevant source urls:
    url_desc, allsources = get_doc_sources(docs2)
    embed.description = f"Sources:\n{url_desc}"
    embed.add_field(
        name="Cache_Query",
        value=f"About {len(docs2)} entries where found.  Max score is {docs2[0][1]}",
    )
    if statmess:
        await statmess.editw(min_seconds=0, content="", embed=embed)
    formatted_docs = []
    for s, v in docs3.items():
        for tup in v:
            doc, _, _ = tup

            meta = doc.metadata
            content = doc.page_content

            sentences = advanced_sentence_splitter(content)
            for e, s in enumerate(sentences):
                output: str = s
                footnote = f"[{e}]({doc.metadata['source']})"

                output = (
                    output.rstrip() + footnote + output[-1]
                    if output and output[-1].isspace()
                    else output + footnote
                )

                formatted_docs.append(output)

    return "  ".join(formatted_docs)
