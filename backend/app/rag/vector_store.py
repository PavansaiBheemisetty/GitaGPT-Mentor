import json
import math
from pathlib import Path

from app.models.corpus import ChunkRecord


class SearchResult:
    def __init__(self, chunk: ChunkRecord, score: float) -> None:
        self.chunk = chunk
        self.score = score


class VectorStore:
    def __init__(self, index_path: Path, metadata_path: Path) -> None:
        self.index_path = index_path
        self.metadata_path = metadata_path
        self._chunks: list[ChunkRecord] = []
        self._index = None
        self._simple_vectors: list[list[float]] = []

    def build(
        self,
        vectors: list[list[float]],
        chunks: list[ChunkRecord],
        *,
        metadata: dict,
        provider: str = "faiss",
    ) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if provider == "faiss":
            try:
                import faiss  # type: ignore
                import numpy as np
            except ImportError as exc:
                raise RuntimeError("faiss-cpu and numpy are required to build a FAISS index.") from exc
            matrix = np.array(vectors, dtype="float32")
            index = faiss.IndexFlatIP(matrix.shape[1])
            index.add(matrix)
            faiss.write_index(index, str(self.index_path))
        else:
            self.index_path.write_text(json.dumps(vectors), encoding="utf-8")
        sidecar = {
            **metadata,
            "vector_store_provider": provider,
            "chunks": [chunk.model_dump() for chunk in chunks],
        }
        self.metadata_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

    def load(self) -> None:
        if not self.index_path.exists() or not self.metadata_path.exists():
            raise FileNotFoundError("Vector index or metadata is missing. Run `python scripts/ingest.py`.")
        metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        self._chunks = [ChunkRecord(**item) for item in metadata["chunks"]]
        if metadata.get("vector_store_provider") == "faiss":
            try:
                import faiss  # type: ignore
            except ImportError as exc:
                raise RuntimeError("faiss-cpu is required to load the FAISS index.") from exc
            self._index = faiss.read_index(str(self.index_path))
        else:
            self._simple_vectors = json.loads(self.index_path.read_text(encoding="utf-8"))

    def search(self, query_vector: list[float], *, top_k: int) -> list[SearchResult]:
        if self._index is not None:
            import numpy as np

            scores, ids = self._index.search(np.array([query_vector], dtype="float32"), top_k)
            results = []
            for score, idx in zip(scores[0], ids[0]):
                if idx >= 0:
                    results.append(SearchResult(self._chunks[int(idx)], float(score)))
            return results

        scored = [
            SearchResult(chunk, _dot(query_vector, vector))
            for chunk, vector in zip(self._chunks, self._simple_vectors)
        ]
        scored.sort(key=lambda result: result.score, reverse=True)
        return scored[:top_k]


def _dot(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / max(math.sqrt(sum(x * x for x in a)), 1e-9)
