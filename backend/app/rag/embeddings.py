import hashlib
import math
from abc import ABC, abstractmethod

from app.core.config import Settings


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
        self.model_name = model_name
        self._model = SentenceTransformer(model_name, device=device)
        # sentence-transformers renamed this method; keep backward compatibility.
        if hasattr(self._model, "get_embedding_dimension"):
            self.dimension = int(self._model.get_embedding_dimension())
        else:
            self.dimension = int(self._model.get_sentence_embedding_dimension())

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=16,
        )
        return [vector.tolist() for vector in vectors]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, api_key: str | None, model_name: str) -> None:
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI embeddings.")
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError("openai package is not installed.") from exc
        self.model_name = model_name
        self._client = OpenAI(api_key=api_key)
        self.dimension = 0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self.model_name, input=texts)
        vectors = [item.embedding for item in response.data]
        if vectors and not self.dimension:
            self.dimension = len(vectors[0])
        return vectors


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    provider = settings.embedding_provider.lower()
    if provider in {"hash", "local-hash"}:
        return HashEmbeddingProvider(dimension=settings.embedding_dimension or 384)
    if provider in {"sentence-transformers", "bge", "local"}:
        return SentenceTransformersProvider(settings.embedding_model, device=settings.embedding_device)
    if provider == "openai":
        return OpenAIEmbeddingProvider(settings.openai_api_key, settings.openai_embedding_model)
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
