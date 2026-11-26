import logging
import threading
from uuid import uuid5, NAMESPACE_URL
from flask import current_app
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding
from .portfolio import all_searchable_records

logger = logging.getLogger(__name__)
_client = None
_embedding_model = None
_initialized_collections = set()
_collection_init_lock = threading.RLock()


def _get_client():
    global _client
    if _client is None:
        url = current_app.config.get("QDRANT_URL", "").strip()
        api_key = current_app.config.get("QDRANT_API_KEY", "").strip()
        if not url:
            raise RuntimeError("QDRANT_URL must be configured.")
        _client = QdrantClient(url=url, api_key=api_key or None, timeout=20)
    return _client


def _get_embedder():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = TextEmbedding(model_name=current_app.config.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    return _embedding_model


def _collection_name():
    return current_app.config.get("QDRANT_COLLECTION", "folioport_portfolio")


def _ensure_collection(client, vector_size=None):
    name = _collection_name()
    cache_key = (id(client), name)
    with _collection_init_lock:
        if cache_key in _initialized_collections:
            return
        existing = {c.name for c in client.get_collections().collections}
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(size=vector_size or 384, distance=models.Distance.COSINE),
            )
        for field_name, schema in (
            ("is_public", models.PayloadSchemaType.BOOL),
            ("entity_kind", models.PayloadSchemaType.KEYWORD),
            ("entity_id", models.PayloadSchemaType.KEYWORD),
        ):
            client.create_payload_index(
                collection_name=name,
                field_name=field_name,
                field_schema=schema,
                wait=True,
            )
        _initialized_collections.add(cache_key)


def _point_id(kind, entity_id, chunk_index):
    return str(uuid5(NAMESPACE_URL, f"folioport:{kind}:{entity_id}:{chunk_index}"))


def _chunks(text, max_chars=1400, overlap=160):
    text = (text or "").strip()
    if not text:
        return []
    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    chunks, current = [], ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            step = max_chars - overlap
            for start in range(0, len(paragraph), step):
                piece = paragraph[start:start + max_chars].strip()
                if piece:
                    chunks.append(piece)
            continue
        if current and len(current) + len(paragraph) + 1 > max_chars:
            chunks.append(current)
            tail = current[-overlap:] if overlap else ""
            current = (tail + "\n" + paragraph).strip() if tail else paragraph
        else:
            current = (current + "\n" + paragraph).strip()
    if current:
        chunks.append(current)
    return chunks


def sync_entity(kind, entity_id):
    """Replace vectors for one database entity. SQL writes succeed if indexing is offline."""
    return sync_entities([(kind, entity_id)])


def sync_entities(entities):
    """Refresh several entities with one database scan and embedding pass."""
    entities = list(entities)
    try:
        entity_keys = {(str(kind), str(entity_id)) for kind, entity_id in entities}
        if not entity_keys:
            return {"indexed": 0, "warning": None}
        records = all_searchable_records(
            public_only=False,
            entity_keys=entity_keys,
        )
        client = _get_client()
        points, texts, metadata = [], [], []
        for record in records:
            content_chunks = _chunks(record["text"])
            for idx, content in enumerate(content_chunks):
                texts.append(content)
                metadata.append({
                    "entity_kind": record["kind"], "entity_id": str(record["id"]), "chunk_index": idx,
                    "title": record["title"], "text": content, "is_public": bool(record["is_public"]),
                })
        vectors = list(_get_embedder().embed(texts)) if texts else []
        points = [
            models.PointStruct(
                id=_point_id(payload["entity_kind"], payload["entity_id"], payload["chunk_index"]),
                vector=vector.tolist(),
                payload=payload,
            )
            for vector, payload in zip(vectors, metadata)
        ]
        _ensure_collection(client, len(vectors[0]) if vectors else None)
        entity_filters = [
            models.Filter(must=[
                models.FieldCondition(key="entity_kind", match=models.MatchValue(value=kind)),
                models.FieldCondition(key="entity_id", match=models.MatchValue(value=entity_id)),
            ])
            for kind, entity_id in entity_keys
        ]
        entity_filter = models.Filter(should=entity_filters)
        client.delete(collection_name=_collection_name(), points_selector=models.FilterSelector(filter=entity_filter), wait=True)
        for start in range(0, len(points), 100):
            client.upsert(collection_name=_collection_name(), points=points[start:start + 100], wait=True)
        return {"indexed": len(points), "warning": None}
    except Exception as exc:  # keep CRUD durable when vector service is temporarily unavailable
        logger.warning("Qdrant index sync failed for %d entities: %s", len(entities), exc)
        return {"indexed": 0, "warning": "Portfolio data was saved, but its search index could not be refreshed. Retry from Admin → Reindex."}


def clear_index():
    """Prepare an empty collection before a durable reindex job processes its batches."""
    client = _get_client()
    vector = next(_get_embedder().embed(["Folioport search index initialization"])).tolist()
    name = _collection_name()
    existing = {collection.name for collection in client.get_collections().collections}
    if name in existing:
        client.delete_collection(collection_name=name)
    with _collection_init_lock:
        _initialized_collections.discard((id(client), name))
    _ensure_collection(client, len(vector))


def reindex_all():
    records = all_searchable_records(public_only=False)
    client = _get_client()
    # Embed first, so a failed embedding initialization does not destroy the current index.
    all_texts, all_meta = [], []
    for record in records:
        for idx, chunk in enumerate(_chunks(record["text"])):
            all_texts.append(chunk)
            all_meta.append({
                "entity_kind": record["kind"], "entity_id": str(record["id"]), "chunk_index": idx,
                "title": record["title"], "text": chunk, "is_public": bool(record["is_public"]),
            })
    vectors = list(_get_embedder().embed(all_texts)) if all_texts else []
    name = _collection_name()
    existing = {c.name for c in client.get_collections().collections}
    with _collection_init_lock:
        _initialized_collections.discard((id(client), name))
    if name in existing:
        client.delete_collection(collection_name=name)
    _ensure_collection(client, len(vectors[0]) if vectors else None)
    points = [models.PointStruct(id=_point_id(meta["entity_kind"], meta["entity_id"], meta["chunk_index"]), vector=vector.tolist(), payload=meta) for vector, meta in zip(vectors, all_meta)]
    for start in range(0, len(points), 100):
        client.upsert(collection_name=name, points=points[start:start + 100], wait=True)
    return {"indexed": len(points), "entities": len(records)}


def retrieve(query, limit=5, public_only=True):
    client = _get_client()
    vector = next(_get_embedder().embed([query])).tolist()
    _ensure_collection(client, len(vector))
    result_limit = max(1, min(int(limit), 20))
    query_filter = None
    if public_only:
        query_filter = models.Filter(must=[models.FieldCondition(key="is_public", match=models.MatchValue(value=True))])
    result = client.query_points(
        collection_name=_collection_name(), query=vector, query_filter=query_filter,
        limit=result_limit * 4, with_payload=True, timeout=8,
    )
    return _format_hits(result.points, result_limit, public_only)


def retrieve_many(queries, limit=5, public_only=True):
    query_texts = [str(query).strip() for query in queries if isinstance(query, str) and query.strip()]
    if not query_texts:
        return []
    if len(query_texts) > 20:
        raise ValueError("A maximum of 20 semantic retrieval queries is allowed.")

    client = _get_client()
    vectors = list(_get_embedder().embed(query_texts))
    if len(vectors) != len(query_texts):
        raise RuntimeError("The embedding model returned an unexpected number of vectors.")
    _ensure_collection(client, len(vectors[0]))
    result_limit = max(1, min(int(limit), 20))
    query_filter = None
    if public_only:
        query_filter = models.Filter(must=[
            models.FieldCondition(key="is_public", match=models.MatchValue(value=True))
        ])
    requests = [
        models.QueryRequest(
            query=vector.tolist(),
            filter=query_filter,
            limit=result_limit * 4,
            with_payload=True,
        )
        for vector in vectors
    ]
    results = client.query_batch_points(
        collection_name=_collection_name(),
        requests=requests,
        timeout=8,
    )
    if len(results) != len(query_texts):
        raise RuntimeError("The vector database returned an unexpected number of query results.")
    return [
        _format_hits(result.points, result_limit, public_only)
        for result in results
    ]


def _format_hits(points, result_limit, public_only):
    hits = []
    seen_entities = set()
    for point in points:
        payload = point.payload or {}
        text = payload.get("text")
        if public_only and payload.get("is_public") is not True:
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        identity = (payload.get("entity_kind", ""), str(payload.get("entity_id", "")))
        if identity in seen_entities:
            continue
        seen_entities.add(identity)
        hits.append({
            "score": float(point.score),
            "title": payload.get("title", "Portfolio record"),
            "text": text,
            "kind": payload.get("entity_kind", ""),
            "entity_id": payload.get("entity_id"),
            "is_public": payload.get("is_public", False),
        })
        if len(hits) >= result_limit:
            break
    return hits
