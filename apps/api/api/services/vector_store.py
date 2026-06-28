"""Vector store abstraction + ChromaDB implementation."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import chromadb

from api.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


class BaseVectorStore(ABC):
    """Pluggable vector store interface."""

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None: ...

    @abstractmethod
    async def query(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]: ...


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB implementation — HTTP server or persistent on-disk."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        persist_dir: str | None = None,
    ):
        self.host = host or _settings.chroma_host
        self.port = port or _settings.chroma_port
        self.persist_dir = persist_dir or _settings.chroma_persist_dir
        try:
            self._client = chromadb.HttpClient(host=self.host, port=self.port)
            self._client.heartbeat()
            self._mode = "http"
        except Exception:
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._mode = "persistent"
            logger.info("ChromaDB running in persistent mode at %s", self.persist_dir)

    def get_or_create_collection(self, name: str):
        return self._client.get_or_create_collection(
            name=name, metadata={"hnsw:space": "cosine"}
        )

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        coll = self.get_or_create_collection(collection)
        coll.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    async def query(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        coll = self.get_or_create_collection(collection)
        res = coll.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
        )
        out: list[dict[str, Any]] = []
        ids = res.get("ids", [[]])[0]
        dists = res.get("distances", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        for i, _id in enumerate(ids):
            out.append(
                {
                    "id": _id,
                    "score": 1.0 - dists[i] if i < len(dists) else 0.0,
                    "document": docs[i] if i < len(docs) else None,
                    "metadata": metas[i] if i < len(metas) else {},
                }
            )
        return out
