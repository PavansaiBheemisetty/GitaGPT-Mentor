import hashlib
import logging
import math
from abc import ABC, abstractmethod

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    model_name: str
    dimension: int

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    def __init__(self, dimension: int = 384) -> None:
        self.model_name = "hash-local-dev"
        self.dimension = dimension
        logger.info("[Embeddings] Hash fallback provider initialized (dim=%d).", dimension)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [_normalize(_hash_vector(text, self.dimension)) for text in texts]


class SentenceTransformersProvider(EmbeddingProvider):
    def __init__(self, model_name: str, device: str = "cpu") -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Install backend dependencies first."
            ) from exc
        logger.info(
            "[Embeddings] Loading HF model '%s' into RAM on device='%s'...",
            model_name, device,
        )
        self.model_name = model_name
        self._model = SentenceTransformer(model_name, device=device)
        # sentence-transformers renamed this method; keep backward compatibility.
        if hasattr(self._model, "get_embedding_dimension"):
            self.dimension = int(self._model.get_embedding_dimension())
        else:
            self.dimension = int(self._model.get_sentence_embedding_dimension())
        logger.info(
            "[Embeddings] ✅ HF model '%s' loaded into RAM successfully (dim=%d, device=%s).",
            model_name, self.dimension, device,
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=16,
        )
        return [vector.tolist() for vector in vectors]


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.lower()
    if provider in {"hash", "local-hash"}:
        logger.info("[Embeddings] Using hash fallback provider.")
        return HashEmbeddingProvider(dimension=settings.embedding_dimension or 384)
    if provider in {"sentence-transformers", "bge", "local"}:
        logger.info("[Embeddings] Creating sentence-transformers provider for model '%s'.", settings.embedding_model)
        return SentenceTransformersProvider(settings.embedding_model, device=settings.embedding_device)
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")


def _hash_vector(text: str, dimension: int) -> list[float]:
    vector = [0.0] * dimension
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    return vector


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
