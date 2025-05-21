import datetime
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Tuple,
)
import uuid
import warnings

from langchain_core.documents import Document
from langchain_core.utils import xor_args
from langchain_core.runnables.config import run_in_executor

from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores.utils import maximal_marginal_relevance
import numpy as np

import lancedb
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import LanceDB

import gui

"""
Class extensions that assist with the LanceBD vector store.


"""


DocumentScoreVector = Tuple[Document, float]


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


class LanceTools:
    """Class full of static methods for simple Lance DB ops."""

    @staticmethod
    def get_lance_client() -> lancedb.DBConnection:
        """Create a new Lance client."""
        client = lancedb.connect(uri="saveData/lance-db")
        return client

    @staticmethod
    async def get_async_client() -> lancedb.AsyncConnection:
        """Create a new Lance client asynchronously."""
        client = await lancedb.connect_async(uri="saveData/lance-db")
        return client

    @staticmethod
    def get_collection(
        collection: str = "web_collection",
        embed: Optional[OpenAIEmbeddings] = None,
        metadata: Optional[dict] = None,
        path: str = "saveData",
    ) -> "LanceBetter":
        """Create a collection for LanceBetter with default configurations.

        Args:
            collection: The name of the collection to retrieve or create.
            embed: The embedding model to use.
            metadata: Metadata associated with the collection. Defaults to None.
            path: The path to the database. Defaults to "saveData".

        Returns:
            An instance of LanceBetter.
        """
        if embed is None:
            embed = OpenAIEmbeddings(model="text-embedding-3-small")
        client = lancedb.connect(uri=f"{path}/lance-db")
        vs = LanceBetter(
            connection=client,
            embedding=embed,
            table_name=collection,
            id_key="id",
            vector_key="vector",
            text_key="text",
            mode="overwrite",
        )
        return vs

    @staticmethod
    def configure_lance_client(
        client: lancedb.DBConnection,
        collection: str = "web_collection",
        embed: Optional[OpenAIEmbeddings] = None,
        metadata: Optional[dict] = None,
        path: str = "saveData",
    ) -> "LanceBetter":
        """Configures the lance client for specific collection.

        Args:
            client: The LanceDBConnection client.
            collection: The name of the collection to use.
            embed: The embedding model to use.
            metadata: Metadata associated with the collection.
            path: The path to the database.

        Returns:
            An instance of LanceBetter configured for the specified collection.
        """
        if embed is None:
            embed = OpenAIEmbeddings(model="text-embedding-3-small")

        vs = LanceBetter(
            connection=client,
            embedding=embed,
            table_name=collection,
            id_key="id",
            vector_key="vector",
            text_key="text",
            mode="overwrite",
        )
        return vs


class LanceClient:
    def __init__(self, path):
        client = lancedb.connect(uri="saveData/lance-db")
        self._data = {}


class LanceBetter(LanceDB):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.upsert_mode = True
        self._data = {}

    def optimize_table(self, name: Optional[str] = None) -> None:
        table = self.get_table(name)
        table.optimize(cleanup_older_than=datetime.timedelta(days=0))

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> List[str]:
        """Turn texts into embeddings and add them to the database.

        Args:
            texts: Iterable of strings to add to the vectorstore.
            metadatas: Optional list of metadatas associated with the texts.
            ids: Optional list of ids to associate with the texts.

        Returns:
            List of ids of the added texts.
        """
        docs = []
        ids = ids or [str(uuid.uuid4()) for _ in texts]
        embeddings = self._embedding.embed_documents(list(texts))  # type: ignore
        for idx, text in enumerate(texts):
            embedding = embeddings[idx]
            metadata = metadatas[idx] if metadatas else {}
            target_doc = {
                self._vector_key: embedding,
                self._id_key: ids[idx],
                self._text_key: text,
            }
            # This is easier for lancedb.
            # Having a metadata struct causes all kinds of issues.

            for i, v in metadata.items():
                target_doc[i] = v
            docs.append(target_doc)

        tbl = self.get_table()

        if tbl is None:
            tbl = self._connection.create_table(self._table_name, data=docs)
            self._table = tbl
        else:
            if self.api_key is None:
                if self._id_key:
                    (
                        tbl.merge_insert(self._id_key)
                        .when_matched_update_all()
                        .when_not_matched_insert_all()
                        .execute(docs)
                    )
                else:
                    tbl.add(docs, mode=self.mode)
            else:
                tbl.add(docs)

        self._fts_index = None

        return ids

    def add_documents(self, documents: List[Document], **kwargs: Any) -> List[str]:
        """Add or update documents in the vectorstore.

        Args:
            documents: Documents to add to the vectorstore.
            kwargs: Additional keyword arguments.
                if kwargs contains ids and documents contain ids,
                the ids in the kwargs will receive precedence.

        Returns:
            List of IDs of the added texts.

        Raises:
            ValueError: If the number of ids does not match the number of documents.
        """
        if "ids" not in kwargs:
            ids = [doc.id for doc in documents]

            if any(ids):
                kwargs["ids"] = ids

        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        gui.gprint(texts)
        gui.gprint(metadatas)
        return self.add_texts(texts, metadatas, **kwargs)

    def get_table(
        self, name: Optional[str] = None, set_default: Optional[bool] = False
    ) -> Any:
        """
        Fetches a table object from the database.

        Args:
            name (str, optional): The name of the table to fetch. Defaults to None
                                  and fetches current table object.
            set_default (bool, optional): Sets fetched table as the default table.
                                          Defaults to False.

        Returns:
            Any: The fetched table object.

        Raises:
            ValueError: If the specified table is not found in the database.
        """
        if name is not None:
            if set_default:
                self._table_name = name
                _name = self._table_name
            else:
                _name = name
        else:
            _name = self._table_name
        try:
            if _name in self._data:
                return self._data[_name]
            tab = self._connection.open_table(_name)
            self._data[_name] = tab
            return tab
        except Exception as e:
            print(e)
            return None

    def get_metadata(self, results, inc: List[str] = []) -> List[Dict[str, Any]]:
        """
        Extract metadata from a LanceDB table query based on column names.
        It's easier on maintaining lancedb tables if the metadata
        ISN'T wrapped inside a single "metadata" field struct.
        Args:
            results: The results from a LanceDB table query.
            inc: A list of column names to include in the metadata extraction,
                 excluding the default vector, id, and text keys.

        Returns:
            A list of dictionaries where each dictionary contains the metadata
            for a corresponding row in the results.
        """
        exclude = {self._vector_key, self._id_key, self._text_key}
        exclude.update(inc)

        metadata_rows = []
        for idx in range(len(results)):
            metadata = {
                key: results[key][idx].as_py()
                for key in results.schema.names
                if key not in exclude
            }
            metadata_rows.append(metadata)
        return metadata_rows

    def results_to_docs(self, results: Any, score: bool = False) -> Any:
        columns = results.schema.names

        if "_distance" in columns:
            score_col = "_distance"
        elif "_relevance_score" in columns:
            score_col = "_relevance_score"
        else:
            score_col = None

        # It's easier on lancedb if the metadata fields
        # aren't wrapped in a struct.

        metadata_list = self.get_metadata(results)

        if score_col is None or not score:
            return [
                Document(
                    page_content=results[self._text_key][idx].as_py(),
                    metadata=metadata_list[idx],
                )
                for idx in range(len(results))
            ]
        else:
            return [
                (
                    Document(
                        page_content=results[self._text_key][idx].as_py(),
                        metadata=metadata_list[idx],
                    ),
                    results[score_col][idx].as_py(),
                )
                for idx in range(len(results))
            ]

    async def aget_by_ids(self, tablestr: str, ids: Sequence[str]) -> List[Document]:
        table = self.get_table(tablestr)
        ids_filter = " OR ".join(f"id = '{id_}'" for id_ in ids)
        outputs = table.search().where(ids_filter).limit(20).to_arrow()
        docs = self.results_to_docs(outputs, score=False)
        return docs

    def get(
        self, filter: Optional[Any] = None, limit: Optional[int] = None
    ) -> List[Document]:
        table = self.get_table()
        outputs = table.search().where(filter).limit(limit).to_arrow()
        docs = self.results_to_docs(outputs, score=False)
        return docs

    async def aget(
        self, filter: Optional[Any] = None, limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Gets the collection asynchronously.

        Args:
            filter: Optional filter criteria.
            limit: The number of documents to return. Optional.

        Returns:
            The filtered collection data.
        """
        return await run_in_executor(
            None,
            self.get,
            filter,
            limit,
        )
