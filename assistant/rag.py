"""Recuperação vetorial para o fluxo de contexto do repositório ChatBot."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from textwrap import wrap
from threading import RLock

import httpx
from fastembed import TextEmbedding
from pymongo import MongoClient

from flora.products import format_brl, normalize_search
from flora.settings import PROJECT_ROOT
from flora.storage import Products


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION = "flora_knowledge"
GUIDES_PATH = Path(__file__).with_name("knowledge.json")


@dataclass(frozen=True)
class Retrieval:
    question: str
    context: str
    sources: list[dict]
    indexed_documents: int


class VectorKnowledgeBase:
    def __init__(self, settings):
        headers = {"apikey": settings.supabase_service_key}
        # Chaves legadas service_role também são JWTs.
        if not settings.supabase_service_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {settings.supabase_service_key}"
        self.supabase = httpx.Client(
            base_url=f"{settings.supabase_url}/rest/v1", headers=headers, timeout=15,
        )
        self.mongo = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, timeoutMS=7000)
        self.products = Products(self.mongo[settings.mongodb_database].products)
        self.lock = RLock()
        self.model = TextEmbedding(
            model_name=MODEL_NAME, cache_dir=str(PROJECT_ROOT / ".assistant_data" / "models"), threads=2,
        )

    def _documents(self, products):
        documents = json.loads(GUIDES_PATH.read_text(encoding="utf-8"))
        for product in products:
            documents.append({
                "id": f"product-{product.id}", "title": product.name,
                "content": (
                    f"Planta: {product.name}. Nome científico: {product.scientific_name}. "
                    f"Categoria: {product.category}. Descrição: {product.description or 'Não informada.'}"
                ),
                "source_url": "",
                "product_id": product.id,
            })
        chunks = []
        for document in documents:
            for index, content in enumerate(wrap(document["content"], width=420, break_long_words=False)):
                chunk = {
                    **document, "id": f"{document['id']}-chunk-{index}", "content": content,
                    "product_id": document.get("product_id"), "embedding_model": MODEL_NAME,
                }
                canonical = json.dumps(chunk, sort_keys=True, ensure_ascii=False)
                chunk["content_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
                chunks.append(chunk)
        return chunks

    def _sync(self, products):
        documents = self._documents(products)
        response = self.supabase.get(f"/{COLLECTION}", params={"select": "id,content_hash,embedding_model"})
        response.raise_for_status()
        existing = {document["id"]: document for document in response.json()}
        changed = [document for document in documents if (
            existing.get(document["id"], {}).get("content_hash") != document["content_hash"]
            or existing.get(document["id"], {}).get("embedding_model") != MODEL_NAME
        )]
        if changed:
            embeddings = self.model.embed([f"{item['title']}\n{item['content']}" for item in changed])
            records = [
                {**document, "embedding": vector.tolist(), "updated_at": datetime.now(UTC).isoformat()}
                for document, vector in zip(changed, embeddings)
            ]
            response = self.supabase.post(
                f"/{COLLECTION}", params={"on_conflict": "id"}, json=records,
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )
            response.raise_for_status()
        removed = existing.keys() - {document["id"] for document in documents}
        for document_id in removed:
            response = self.supabase.delete(f"/{COLLECTION}", params={"id": f"eq.{document_id}"})
            response.raise_for_status()
        return len(documents)

    def sync(self):
        with self.lock:
            return self._sync(self.products.list())

    def retrieve(self, question, previous_question=""):
        with self.lock:
            products = self.products.list()
            count = self._sync(products)
            search_text = f"{previous_question}\n{question}".strip()
            embedding = next(self.model.embed([search_text])).tolist()
            response = self.supabase.post("/rpc/match_flora_knowledge", json={
                "query_embedding": embedding, "model_name": MODEL_NAME,
                "match_count": 6, "min_similarity": 0.25,
            })
            response.raise_for_status()
            matches = response.json()
            normalized = f" {normalize_search(search_text)} "
            named_matches = []
            for product in products:
                names = (product.name, product.scientific_name)
                if any(name and f" {normalize_search(name)} " in normalized for name in names):
                    response = self.supabase.get(f"/{COLLECTION}", params={
                        "product_id": f"eq.{product.id}",
                        "select": "id,title,content,source_url,product_id",
                    })
                    response.raise_for_status()
                    named_matches.extend({**item, "similarity": None} for item in response.json())
            named_ids = {match["id"] for match in named_matches}
            matches = (named_matches + [match for match in matches if match["id"] not in named_ids])[:6]

        by_id = {product.id: product for product in products}
        context = []
        sources = []
        for match in matches:
            product_id = match.get("product_id")
            if product_id and product_id not in by_id:
                continue
            number = len(sources) + 1
            text = f"[{number}] {match['title']}\n{match['content']}"
            if product_id:
                text += f"\nPreço atual: {format_brl(by_id[product_id].price_cents)}."
            context.append(text)
            sources.append({
                "number": number, "title": match["title"], "url": match["source_url"],
                "similarity": round(match["similarity"], 4) if match["similarity"] is not None else None,
            })
        return Retrieval(question, "\n\n".join(context), sources, count)

    def close(self):
        self.supabase.close()
        self.mongo.close()
