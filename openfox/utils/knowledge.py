import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from agno.knowledge.document import Document
from agno.knowledge.embedder.base import Embedder
from agno.knowledge.reranker.base import Reranker
from agno.utils.log import logger

try:
    import litellm
except ImportError as e:
    raise ImportError("`litellm` not installed. Please install it via `pip install litellm`.") from e

# Suppress LiteLLM's extra debug/help text output on exceptions.
litellm.suppress_debug_info = True


class _LiteLLMRerankDashscopeFilter(logging.Filter):
    """Filter out known noisy LiteLLM dashscope rerank error."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return (
            "LiteLLM rerank error: litellm.APIConnectionError: Unsupported provider: dashscope"
            not in message
        )


def _configure_knowledge_logger_filter() -> None:
    for f in logger.filters:
        if isinstance(f, _LiteLLMRerankDashscopeFilter):
            return
    logger.addFilter(_LiteLLMRerankDashscopeFilter())


_configure_knowledge_logger_filter()


@dataclass
class LiteLLMEmbedder(Embedder):
    """Embedder implementation backed by LiteLLM unified interface.

    This enables using any embedding provider supported by LiteLLM with a single
    configuration surface. You can supply any provider specific model string that
    LiteLLM understands, for example:
        - openai/text-embedding-3-small
        - openai/text-embedding-3-large
        - cohere/embed-english-v3.0
        - jina/jina-embeddings-v2-base-en

    Args:
        id: The LiteLLM model identifier.
        api_key: Optional API key (falls back to environment variables recognized by LiteLLM).
        api_base: Optional custom base URL.
        request_params: Extra parameters forwarded to litellm.embedding / aembedding.
        enable_batch: Whether batch embedding helper should be used.
        batch_size: Batch size for async batch helper.
    """

    id: str = "openai/text-embedding-3-small"
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    request_params: Optional[Dict[str, Any]] = None
    enable_batch: bool = False
    batch_size: int = 100

    def _build_request(self, texts: List[str]) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "model": self.id,
            "input": texts,
        }
        if self.api_key is not None:
            params["api_key"] = self.api_key
        if self.api_base is not None:
            params["api_base"] = self.api_base
        if self.request_params:
            params.update(self.request_params)
        return params

    @staticmethod
    def _extract_embedding(response: Any) -> List[float]:
        """Extract first embedding from LiteLLM embedding response."""
        try:
            data = response.get("data") if isinstance(response, dict) else getattr(response, "data", None)
            if not isinstance(data, list) or not data:
                return []
            item = data[0]
            emb = item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", None)
            return list(emb) if isinstance(emb, list) else []
        except Exception as e:
            logger.warning("Failed to extract embedding: %s", e)
            return []

    @staticmethod
    def _extract_usage(response: Any) -> Optional[Dict[str, Any]]:
        """Extract usage information from LiteLLM response."""
        try:
            if response is None:
                return None
            if isinstance(response, dict):
                u = response.get("usage")
                if isinstance(u, dict):
                    return u
                return None
            usage = getattr(response, "usage", None)
            if usage is None:
                return None
            if isinstance(usage, dict):
                return usage
            if hasattr(usage, "model_dump"):
                return usage.model_dump()
            return None
        except Exception as e:
            logger.warning("Failed to extract usage: %s", e)
            return None

    def get_embedding(self, text: str) -> List[float]:
        try:
            request = self._build_request([text])
            response = litellm.embedding(**request)
            return self._extract_embedding(response)
        except Exception as e:
            logger.warning(f"LiteLLM embedding error: {e}")
            return []

    def get_embedding_and_usage(self, text: str) -> Tuple[List[float], Optional[Dict]]:
        try:
            request = self._build_request([text])
            response = litellm.embedding(**request)
            embedding = self._extract_embedding(response)
            usage = self._extract_usage(response)
            return embedding, usage
        except Exception as e:
            logger.warning(f"LiteLLM embedding error: {e}")
            return [], None

    async def async_get_embedding(self, text: str) -> List[float]:
        try:
            request = self._build_request([text])
            response = await litellm.aembedding(**request)
            return self._extract_embedding(response)
        except Exception as e:
            logger.warning(f"LiteLLM async embedding error: {e}")
            return []

    async def async_get_embedding_and_usage(self, text: str) -> Tuple[List[float], Optional[Dict]]:
        try:
            request = self._build_request([text])
            response = await litellm.aembedding(**request)
            embedding = self._extract_embedding(response)
            usage = self._extract_usage(response)
            return embedding, usage
        except Exception as e:
            logger.warning(f"LiteLLM async embedding error: {e}")
            return [], None

    async def async_get_embeddings_batch_and_usage(
        self, texts: List[str]
    ) -> Tuple[List[List[float]], List[Optional[Dict]]]:
        """Batch async embedding helper using LiteLLM.

        Falls back to individual calls on failure to maximize resilience.
        """
        all_embeddings: List[List[float]] = []
        all_usage: List[Optional[Dict]] = []

        logger.info(
            f"Getting embeddings and usage for {len(texts)} texts in batches of {self.batch_size} (LiteLLM async)"
        )
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            try:
                request = self._build_request(batch)
                response = await litellm.aembedding(**request)
                raw = response.get("data") if isinstance(response, dict) else getattr(response, "data", None)
                embeddings: List[List[float]] = []
                if isinstance(raw, list):
                    for item in raw:
                        e = item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", None)
                        embeddings.append(list(e) if isinstance(e, list) else [])
                usage = self._extract_usage(response)
                all_embeddings.extend(embeddings)
                all_usage.extend([usage] * len(embeddings))
            except Exception as e:
                logger.warning(f"LiteLLM batch embedding error: {e} - falling back to per item")
                for t in batch:
                    emb, usage = await self.async_get_embedding_and_usage(t)
                    all_embeddings.append(emb)
                    all_usage.append(usage)
        return all_embeddings, all_usage


class LiteLLMReranker(Reranker):
    """Reranker using LiteLLM ``litellm.rerank``."""

    model: str = "cohere/rerank-multilingual-v3.0"
    top_n: Optional[int] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    request_params: Optional[Dict[str, Any]] = None

    def _build_request(self, query: str, documents: List[Document]) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "model": self.model,
            "query": query,
            "documents": [d.content for d in documents],
        }
        if self.top_n and self.top_n > 0:
            params["top_n"] = self.top_n
        if self.api_key is not None:
            params["api_key"] = self.api_key
        if self.api_base is not None:
            params["api_base"] = self.api_base
        if self.request_params:
            params.update(self.request_params)
        return params

    @staticmethod
    def _extract_results(response: Any) -> List[Any]:
        try:
            if hasattr(response, "results"):
                return response.results
            return []
        except Exception:
            return []

    def _rerank(self, query: str, documents: List[Document]) -> List[Document]:
        if not documents:
            return []
        try:
            request = self._build_request(query=query, documents=documents)
            response = litellm.rerank(**request)
            results = self._extract_results(response)
            ranked: List[Document] = []
            for r in results:
                try:
                    idx = getattr(r, "index", None)
                    score = getattr(r, "relevance_score", None)
                    if idx is None or idx >= len(documents):
                        continue
                    doc = documents[idx]
                    doc.reranking_score = score
                    ranked.append(doc)
                except Exception as e:
                    logger.warning("Failed processing rerank item: %s", e)

            ranked.sort(
                key=lambda d: d.reranking_score if d.reranking_score is not None else float("-inf"),
                reverse=True,
            )
            if self.top_n and self.top_n > 0:
                ranked = ranked[: self.top_n]
            return ranked
        except Exception as e:
            logger.error("LiteLLM rerank error: %s. Returning original documents", e)
            return documents

    def rerank(self, query: str, documents: List[Document]) -> List[Document]:
        try:
            return self._rerank(query=query, documents=documents)
        except Exception as e:
            logger.error("Unexpected rerank error: %s. Returning original documents", e)
            return documents