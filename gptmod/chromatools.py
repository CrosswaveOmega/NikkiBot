"""
Class extensions that assist with the Chromadb vector store.


"""

from datetime import timedelta, timezone, datetime
import json
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
)
import warnings
import discord
import io
import chromadb
from chromadb.types import Vector
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.utils import xor_args
from langchain_core.runnables.config import run_in_executor
from langchain.vectorstores.chroma import Chroma
from chromadb.utils.batch_utils import create_batches
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.utils import maximal_marginal_relevance
from chromadb.config import Settings
import numpy as np


DocumentScoreVector = Tuple[Document, float, Vector]


def _results_to_docs_scores_emb(results: Any) -> List[DocumentScoreVector]:
    return [
        (
            Document(page_content=result[0], metadata=result[1] or {}),
            result[2],
            result[3],
        )
        for result in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
            results["embeddings"][0],
        )
    ]


DEFAULT_K = 4  # Number of Documents to return.


class ChromaTools:
    """Class full of static methods for simple Chroma DB ops."""

    @staticmethod
    def get_chroma_client() -> chromadb.ClientAPI:
        """Create a new chroma client."""
        client = chromadb.PersistentClient(path="saveData")
        return client

    @staticmethod
    def get_collection(
        collection="web_collection", embed=None, metadata=None, path="saveData"
    ):
        client = chromadb.PersistentClient(
            path=path, settings=Settings(anonymized_telemetry=False)
        )

        if embed is None:
            embed = OpenAIEmbeddings(model="text-embedding-3-small")
        vs = ChromaBetter(
            client=client,
            persist_directory=path,
            embedding_function=embed,
            collection_name=collection,
            collection_metadata=metadata,
        )
        return vs


class ChromaBetter(Chroma):
    """Extension of Langchain's Chroma class that will return the
    embeddings as well as the Document distance."""

    def add_documents(self, documents: List[Document], ids: List[str]):
        if len(documents) != len(ids):
            raise Exception("Documents does not match ids!")
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        max_batch = 200
        if hasattr(self._client, "max_batch_size"):
            max_batch = self._client.max_batch_size
        if max_batch < len(documents):
            for batch in create_batches(
                api=self._client,
                ids=ids,
                metadatas=metadatas,
                documents=texts,
            ):
                self.add_texts(
                    texts=batch[3] if batch[3] else [],
                    metadatas=batch[2] if batch[2] else None,
                    ids=batch[0],
                )
        else:
            self.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    async def aadd_documents(self, documents: List[Document], ids: List[str]):
        if len(documents) != len(ids):
            raise Exception("Documents does not match ids!")
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        max_batch = 200
        if hasattr(self._client, "max_batch_size"):
            max_batch = self._client.max_batch_size
        if max_batch < len(documents):
            for batch in create_batches(
                api=self._client,
                ids=ids,
                metadatas=metadatas,
                documents=texts,
            ):
                await self.aadd_texts(
                    texts=batch[3] if batch[3] else [],
                    metadatas=batch[2] if batch[2] else None,
                    ids=batch[0],
                )
        else:
            await self.aadd_texts(texts=texts, metadatas=metadatas, ids=ids)

    @xor_args(("query_texts", "query_embeddings"))
    def __query_collection(
        self,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 4,
        where: Optional[Dict[str, str]] = None,
        where_document: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Query the chroma collection."""

        return self._collection.query(
            query_texts=query_texts,
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            where_document=where_document,
            **kwargs,
        )

    async def asimilarity_search_with_score_and_embedding(
        self, *args: Any, **kwargs: Any
    ) -> List[DocumentScoreVector]:
        """Run similarity search with distance asynchronously."""

        # This is a temporary workaround to make the similarity search
        # asynchronous. The proper solution is to make the similarity search
        # asynchronous in the vector store implementations.
        return await run_in_executor(
            None, self.similarity_search_with_score_and_embedding, *args, **kwargs
        )

    async def _asimilarity_search_with_relevance_scores_and_embeddings(
        self,
        query: str,
        k: int = 4,
        **kwargs: Any,
    ) -> List[DocumentScoreVector]:
        relevance_score_fn = self._select_relevance_score_fn()
        docs_and_scores = await self.asimilarity_search_with_score_and_embedding(
            query, k, **kwargs
        )
        return [
            (doc, relevance_score_fn(score), emb) for doc, score, emb in docs_and_scores
        ]

    async def asimilarity_search_with_relevance_scores_and_embeddings(
        self,
        query: str,
        k: int = 4,
        **kwargs: Any,
    ) -> List[DocumentScoreVector]:
        """Return docs and relevance scores in the range [0, 1], asynchronously.

        0 is dissimilar, 1 is most similar.

        Args:
            query: input text
            k: Number of Documents to return. Defaults to 4.
            **kwargs: kwargs to be passed to similarity search. Should include:
                score_threshold: Optional, a floating point value between 0 to 1 to
                    filter the resulting set of retrieved docs

        Returns:
            List of Tuples of (doc, similarity_score)
        """
        score_threshold = kwargs.pop("score_threshold", None)

        docs_and_similarities = (
            await self._asimilarity_search_with_relevance_scores_and_embeddings(
                query, k=k, **kwargs
            )
        )
        if any(
            similarity < 0.0 or similarity > 1.0
            for _, similarity,_ in docs_and_similarities
        ):
            warnings.warn(
                "Relevance scores must be between"
                f" 0 and 1, got {docs_and_similarities}"
            )

        if score_threshold is not None:
            docs_and_similarities = [
                (doc, similarity, emb)
                for doc, similarity, emb in docs_and_similarities
                if similarity >= score_threshold
            ]
            if len(docs_and_similarities) == 0:
                warnings.warn(
                    "No relevant docs were retrieved using the relevance score"
                    f" threshold {score_threshold}"
                )
        return docs_and_similarities


    def similarity_search_with_score_and_embedding(
        self,
        query: str,
        k: int = DEFAULT_K,
        filter: Optional[Dict[str, str]] = None,
        where_document: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> List[DocumentScoreVector]:
        """Run similarity search with Chroma with distance.

        Args:
            query (str): Query text to search for.
            k (int): Number of results to return. Defaults to 4.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List[Tuple[Document, float,Vector]]: List of documents most similar to
            the query text, cosine distance in float for each, and the Embedding.
            Lower score represents more similarity.
        """
        if self._embedding_function is None:
            results = self.__query_collection(
                query_texts=[query],
                n_results=k,
                where=filter,
                where_document=where_document,
                include=["documents", "metadatas", "distances", "embeddings"],
                **kwargs,
            )
        else:
            query_embedding = self._embedding_function.embed_query(query)
            results = self.__query_collection(
                query_embeddings=[query_embedding],
                n_results=k,
                where=filter,
                where_document=where_document,
                include=["documents", "metadatas", "distances", "embeddings"],
                **kwargs,
            )

        return _results_to_docs_scores_emb(results)

    def max_marginal_relevance_search_by_vector(
        self,
        embedding: List[float],
        k: int = DEFAULT_K,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[Dict[str, str]] = None,
        where_document: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> List[DocumentScoreVector]:
        """Return docs selected using the maximal marginal relevance.
        Maximal marginal relevance optimizes for similarity to query AND diversity
        among selected documents.
        Will return the Document, distance, and embedding.

        Args:
            embedding: Embedding to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            fetch_k: Number of Documents to fetch to pass to MMR algorithm.
            lambda_mult: Number between 0 and 1 that determines the degree
                        of diversity among the results with 0 corresponding
                        to maximum diversity and 1 to minimum diversity.
                        Defaults to 0.5.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List of Documents selected by maximal marginal relevance.
        """

        results = self.__query_collection(
            query_embeddings=embedding,
            n_results=fetch_k,
            where=filter,
            where_document=where_document,
            include=["documents", "metadatas", "distances", "embeddings"],
            **kwargs,
        )
        mmr_selected = maximal_marginal_relevance(
            np.array(embedding, dtype=np.float32),
            results["embeddings"][0],
            k=k,
            lambda_mult=lambda_mult,
        )

        candidates = _results_to_docs_scores_emb(results)

        selected_results = [r for i, r in enumerate(candidates) if i in mmr_selected]
        return selected_results

    def max_marginal_relevance_search(
        self,
        query: str,
        k: int = DEFAULT_K,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filter: Optional[Dict[str, str]] = None,
        where_document: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> List[DocumentScoreVector]:
        """Return docs selected using the maximal marginal relevance.
        Maximal marginal relevance optimizes for similarity to query AND diversity
        among selected documents.

        Args:
            query: Text to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            fetch_k: Number of Documents to fetch to pass to MMR algorithm.
            lambda_mult: Number between 0 and 1 that determines the degree
                        of diversity among the results with 0 corresponding
                        to maximum diversity and 1 to minimum diversity.
                        Defaults to 0.5.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List of Documents selected by maximal marginal relevance.
        """
        if self._embedding_function is None:
            raise ValueError(
                "For MMR search, you must specify an embedding function on" "creation."
            )

        embedding = self._embedding_function.embed_query(query)
        docs = self.max_marginal_relevance_search_by_vector(
            embedding,
            k,
            fetch_k,
            lambda_mult=lambda_mult,
            filter=filter,
            where_document=where_document,
        )
        return docs
