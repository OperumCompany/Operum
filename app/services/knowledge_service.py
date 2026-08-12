from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from app.core.config import (
    KNOWLEDGE_BASE_DIR,
    KNOWLEDGE_BASE_ENABLED,
    KNOWLEDGE_MIN_SIMILARITY,
    KNOWLEDGE_SEMANTIC_TOP_K,
    KNOWLEDGE_STRONG_SEMANTIC_SIMILARITY,
)
from app.services.embedding_service import EmbeddingService
from app.services.knowledge_repository import KnowledgeRepository


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower().strip()


LEXICAL_STOPWORDS = {
    "a", "ao", "aos", "as", "como", "com", "da", "das", "de", "do", "dos", "e",
    "em", "esse", "essa", "isso", "me", "meu", "minha", "na", "nas", "no", "nos",
    "o", "os", "para", "por", "porque", "qual", "quais", "que", "se", "ser", "um",
    "uma", "meus", "minhas", "cite", "exemplo", "exemplos", "dois", "duas",
}
GENERIC_FINANCE_TERMS = {
    "ativo", "ativos", "financeiro", "financeiros", "financa", "financas", "investimento",
    "investimentos", "investir", "mercado", "mercados",
}


class KnowledgeService:
    def __init__(self, repository: KnowledgeRepository | None = None, embedder: EmbeddingService | None = None):
        self.enabled = KNOWLEDGE_BASE_ENABLED
        self.repository = repository or KnowledgeRepository()
        self.embedder = embedder or EmbeddingService()
        default_dir = Path(__file__).resolve().parents[2] / "docs" / "knowledge"
        self.base_dir = Path(KNOWLEDGE_BASE_DIR) if KNOWLEDGE_BASE_DIR else default_dir
        self._documents: list[dict] | None = None

    def load_documents(self, force: bool = False) -> list[dict]:
        if self._documents is not None and not force:
            return self._documents
        documents = []
        if not self.base_dir.exists():
            self._documents = []
            return []
        for path in sorted(self.base_dir.glob("*.md")):
            documents.append(self._parse(path))
        ids = [item["id"] for item in documents]
        if len(ids) != len(set(ids)):
            raise ValueError("A base de conhecimento possui IDs duplicados")
        self._documents = documents
        return documents

    def _parse(self, path: Path) -> dict:
        raw = path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, flags=re.DOTALL)
        if not match:
            raise ValueError(f"Metadados ausentes em {path.name}")
        metadata = json.loads(match.group(1))
        body = match.group(2).strip()
        required = {"id", "title", "category", "aliases", "version", "reviewed_at", "sources"}
        missing = required - metadata.keys()
        if missing or not body:
            raise ValueError(f"FAQ invalida em {path.name}: {sorted(missing)}")
        short_match = re.search(r"## Resposta curta\s*\n(.*?)(?=\n## |\Z)", body, flags=re.DOTALL)
        short_answer = short_match.group(1).strip() if short_match else body.split("\n\n", 1)[0]
        explanation_match = re.search(r"## Explica(?:ç|c)ão\s*\n(.*?)(?=\n## |\Z)", body, flags=re.DOTALL | re.IGNORECASE)
        explanation = explanation_match.group(1).strip() if explanation_match else ""
        source_lines = " ".join(source.get("name", "") for source in metadata["sources"])
        search_text = "\n".join([
            metadata["title"], "Perguntas: " + "; ".join(metadata["aliases"]), body, source_lines,
        ])
        content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return {
            **metadata,
            "slug": path.stem,
            "short_answer": short_answer,
            "explanation": explanation,
            "content": body,
            "search_text": search_text,
            "content_hash": content_hash,
            "time_sensitive": bool(metadata.get("time_sensitive", False)),
        }

    def index(self, force: bool = False, category: str | None = None, limit: int | None = None, dry_run: bool = False) -> dict:
        documents = self.load_documents(force=True)
        if category:
            documents = [item for item in documents if normalize_text(item["category"]) == normalize_text(category)]
        if limit:
            documents = documents[:limit]
        if not self.repository.enabled or not self.embedder.enabled:
            return {"status": "disabled", "total": len(documents), "indexed": 0}
        hashes = {} if force else self.repository.existing_hashes()
        pending = [item for item in documents if force or hashes.get(item["id"]) != item["content_hash"]]
        if dry_run:
            return {"status": "dry_run", "total": len(documents), "pending": len(pending), "indexed": 0}
        vectors = self.embedder.encode_passages([item["search_text"] for item in pending])
        entries = []
        for document, vector in zip(pending, vectors, strict=True):
            embedding_hash = hashlib.sha256(
                f"{self.embedder.model_name}:{document['search_text']}".encode("utf-8")
            ).hexdigest()
            entries.append((document, vector, embedding_hash))
        self.repository.upsert_batch(entries)
        return {"status": "ok", "total": len(documents), "pending": 0, "indexed": len(pending)}

    def search(self, query: str, limit: int = KNOWLEDGE_SEMANTIC_TOP_K) -> list[dict]:
        if not self.enabled or not query.strip():
            return []
        documents = self.load_documents()
        normalized_query = normalize_text(query).rstrip("?.!")
        query_tokens = {
            token for token in re.findall(r"[a-z0-9]+", normalized_query)
            if len(token) > 2 and token not in LEXICAL_STOPWORDS and token not in GENERIC_FINANCE_TERMS
        }
        scores: dict[str, float] = {}
        exact_ids = set()
        lexical_ids = set()
        for item in documents:
            aliases = [normalize_text(alias).rstrip("?.!") for alias in item["aliases"]]
            title = normalize_text(item["title"]).rstrip("?.!")
            if normalized_query == title or normalized_query in aliases:
                scores[item["id"]] = 1.0
                exact_ids.add(item["id"])
                continue
            haystack = normalize_text(" ".join([item["title"], *item["aliases"], item["content"]]))
            matched = {token for token in query_tokens if token in haystack}
            coverage = len(matched) / max(1, len(query_tokens))
            if len(matched) >= 2 and coverage >= 0.5:
                scores[item["id"]] = min(0.82, coverage)
                lexical_ids.add(item["id"])
        # Exact FAQ aliases should be instant and do not need to load the local model.
        if not exact_ids and self.repository.enabled and self.embedder.enabled:
            try:
                vector = self.embedder.encode_query(query)
                for row in self.repository.semantic_search(vector, max(8, limit * 2)):
                    similarity = float(row["similarity"])
                    has_lexical_support = row["id"] in lexical_ids
                    if similarity >= KNOWLEDGE_MIN_SIMILARITY and (
                        has_lexical_support or similarity >= KNOWLEDGE_STRONG_SEMANTIC_SIMILARITY
                    ):
                        scores[row["id"]] = max(scores.get(row["id"], 0), similarity)
            except Exception:
                pass
        by_id = {item["id"]: item for item in documents}
        ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:limit]
        return [
            {
                **by_id[item_id],
                "similarity": score,
                "exact_match": item_id in exact_ids,
                "direct_match": item_id in exact_ids,
            }
            for item_id, score in ranked if item_id in by_id
        ]

    @staticmethod
    def render_direct_answer(document: dict) -> str:
        parts = [document.get("short_answer", "").strip()]
        explanation = document.get("explanation", "").strip()
        if explanation and explanation not in parts:
            parts.append(explanation)
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def source_payload(documents: list[dict]) -> list[dict]:
        seen = set()
        result = []
        for document in documents:
            for index, source in enumerate(document["sources"]):
                url = source.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                result.append({
                    "id": f"{document['id']}:source:{index}", "type": "knowledge",
                    "title": document["title"], "source_name": source.get("name", "Fonte institucional"),
                    "source_url": url, "published_at": None, "similarity": document.get("similarity"),
                })
        return result
