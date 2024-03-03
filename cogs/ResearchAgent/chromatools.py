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
import discord
import io
import chromadb
from chromadb.types import Vector
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.utils import xor_args
from langchain_core.runnables.config import run_in_executor
from langchain.vectorstores.chroma import Chroma
chromadb.QueryResult
def _results_to_docs_scores_emb(results: Any) -> List[Tuple[Document, float,Vector]]:
    return [
        # TODO: Chroma can do batch querying,
        # we shouldn't hard code to the 1st result
        (Document(page_content=result[0], metadata=result[1] or {}), result[2],result[3])
        for result in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
            results["embeddings"][0]
        )
    ]

DEFAULT_K = 4  # Number of Documents to return.
class ChromaTools:
    """Class full of static methods for simple Chroma DB ops."""

    @staticmethod
    def get_chroma_client() -> chromadb.ClientAPI:
        '''Create a new chroma client.'''
        client = chromadb.PersistentClient(path="saveData")
        return client
    
class ChromaBetter(Chroma):
    """Extension of Langchain's Chroma class """
    
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
        try:
            import chromadb  # noqa: F401
        except ImportError:
            raise ValueError(
                "Could not import chromadb python package. "
                "Please install it with `pip install chromadb`."
            )
        return self._collection.query(
            query_texts=query_texts,
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=['documents','metadatas','distances','embeddings'],
            **kwargs,
        )

    async def asimilarity_search_with_score_and_embedding(
        self, *args: Any, **kwargs: Any
    ) -> List[Tuple[Document, float,Vector]]:
        """Run similarity search with distance asynchronously."""

        # This is a temporary workaround to make the similarity search
        # asynchronous. The proper solution is to make the similarity search
        # asynchronous in the vector store implementations.
        return await run_in_executor(
            None, self.similarity_search_with_score_and_embedding, *args, **kwargs
        )

    def similarity_search_with_score_and_embedding(
        self,
        query: str,
        k: int = DEFAULT_K,
        filter: Optional[Dict[str, str]] = None,
        where_document: Optional[Dict[str, str]] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float,Vector]]:
        """Run similarity search with Chroma with distance.

        Args:
            query (str): Query text to search for.
            k (int): Number of results to return. Defaults to 4.
            filter (Optional[Dict[str, str]]): Filter by metadata. Defaults to None.

        Returns:
            List[Tuple[Document, float]]: List of documents most similar to
            the query text and cosine distance in float for each.
            Lower score represents more similarity.
        """
        if self._embedding_function is None:
            results = self.__query_collection(
                query_texts=[query],
                n_results=k,
                where=filter,
                where_document=where_document,
                **kwargs,
            )
        else:
            query_embedding = self._embedding_function.embed_query(query)
            results = self.__query_collection(
                query_embeddings=[query_embedding],
                n_results=k,
                where=filter,
                where_document=where_document,
                **kwargs,
            )

        return _results_to_docs_scores_emb(results)