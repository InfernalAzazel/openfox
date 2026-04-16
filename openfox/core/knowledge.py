"""Build Agno ``Knowledge`` + Chroma from OpenFox ``Config`` when ``search_knowledge`` is enabled."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from agno.db.sqlite import AsyncSqliteDb
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.chroma import ChromaDb

from openfox.schemas.config import Config
from openfox.utils.const import CHROMADB_PATH
from openfox.utils.knowledge import LiteLLMEmbedder, LiteLLMReranker


def _nonempty(s: str) -> bool:
    return bool(s and s.strip())


def _embedder_from_config(config: Config) -> LiteLLMEmbedder:
    ec = config.knowledge.vector_db.embedder
    llm = config.llm
    api_key = ec.api_key if _nonempty(ec.api_key) else llm.api_key
    api_base = ec.api_base if _nonempty(ec.api_base) else llm.api_base
    return LiteLLMEmbedder(
        id=ec.id,
        api_key=api_key or None,
        api_base=api_base or None,
        request_params=ec.request_params,
        enable_batch=ec.enable_batch,
        batch_size=ec.batch_size,
    )


def _reranker_from_config(config: Config) -> Optional[LiteLLMReranker]:
    chroma = config.knowledge.vector_db
    if not chroma.reranker_enabled:
        return None
    rc = chroma.reranker
    llm = config.llm
    api_key = rc.api_key if _nonempty(rc.api_key) else llm.api_key
    api_base = rc.api_base if _nonempty(rc.api_base) else llm.api_base
    return LiteLLMReranker(
        model=rc.model,
        top_n=rc.top_n,
        api_key=api_key or None,
        api_base=api_base or None,
        request_params=rc.request_params,
    )


def build_knowledge(config: Config, contents_db: AsyncSqliteDb) -> Optional[Knowledge]:
    """Return a configured ``Knowledge`` instance, or ``None`` when RAG is disabled."""
    if not config.search_knowledge:
        return None

    kcfg = config.knowledge
    vc = kcfg.vector_db
    path = str(CHROMADB_PATH.resolve())
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    embedder = _embedder_from_config(config)
    reranker = _reranker_from_config(config)

    chroma_kw: dict = {
        "collection": vc.collection,
        "name": vc.name,
        "description": vc.description,
        "id": vc.id,
        "embedder": embedder,
        "distance": vc.distance,
        "path": path,
        "persistent_client": vc.persistent_client,
        "search_type": vc.search_type,
        "hybrid_rrf_k": vc.hybrid_rrf_k,
        "batch_size": vc.batch_size,
    }
    if reranker is not None:
        chroma_kw["reranker"] = reranker

    vector_db = ChromaDb(**chroma_kw)

    knowledge = Knowledge(
        name=vc.name,
        description=vc.description,
        contents_db=contents_db,
        vector_db=vector_db,
        max_results=kcfg.max_results,
        isolate_vector_search=kcfg.isolate_vector_search,
    )
    return knowledge
