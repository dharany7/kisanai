"""
rag.py — ChromaDB-backed RAG knowledge base for KisanAI (Phase 5)

Uses sentence-transformers directly for embedding (avoids ChromaDB's
slow ONNX auto-download on first run).

Public interface:
    initialize_knowledge_base() -> chromadb.Collection
    search_knowledge_base(collection, disease_name, n_results=2) -> list[dict]
    get_disease_context(disease_name) -> str
"""

from __future__ import annotations

import logging
from typing import List

import chromadb
from sentence_transformers import SentenceTransformer

from knowledge_base.diseases import DISEASES

logger = logging.getLogger(__name__)

# ChromaDB persistent storage path (relative to project root / cwd)
_CHROMA_DIR = "./chroma_db"
_COLLECTION_NAME = "kisanai_diseases"

# Embedding model — cached after first load
_embedding_model: SentenceTransformer | None = None


def _get_embedding_model() -> SentenceTransformer:
    """Load (and cache) the sentence-transformer embedding model."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading sentence-transformer model …")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding model ready.")
    return _embedding_model


def _embed(texts: list[str]) -> list[list[float]]:
    """Return embeddings as plain Python float lists (ChromaDB format)."""
    model = _get_embedding_model()
    return model.encode(texts, convert_to_numpy=True).tolist()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_document(disease: dict) -> str:
    """Combine key fields into a single searchable text document.

    The disease name is repeated at the start so the embedding space
    anchors strongly to the specific disease, reducing confusion between
    semantically close diseases like Early Blight vs Late Blight.
    """
    return (
        f"{disease['disease']} {disease['disease']}. "
        f"Crop: {disease['crop']}. "
        f"Symptoms: {disease['symptoms']} "
        f"Treatment: {disease['treatment']} "
        f"Prevention: {disease['prevention']}"
    )


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def initialize_knowledge_base() -> chromadb.Collection:
    """
    Create (or re-open) the ChromaDB collection and populate it if empty.

    Embeddings are generated with sentence-transformers locally so that
    ChromaDB does not need to download its own ONNX model at runtime.

    Returns:
        The ChromaDB collection ready for querying.
    """
    # Use chromadb without any built-in embedding function
    client = chromadb.PersistentClient(path=_CHROMA_DIR)
    collection = client.get_or_create_collection(
        name=_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
        embedding_function=None,   # we will supply embeddings ourselves
    )

    if collection.count() > 0:
        logger.info("Knowledge base already loaded (%d diseases)", collection.count())
        print("Knowledge base already loaded")
        return collection

    # Build documents and IDs from the DISEASES list
    documents: list[str] = []
    ids: list[str] = []

    for disease in DISEASES:
        documents.append(_build_document(disease))
        ids.append(disease["id"])

    # Generate embeddings via sentence-transformers
    logger.info("Generating embeddings for %d disease entries …", len(documents))
    embeddings = _embed(documents)

    collection.add(documents=documents, ids=ids, embeddings=embeddings)

    logger.info("Knowledge base loaded with %d diseases", len(documents))
    print(f"Knowledge base loaded with {len(documents)} diseases")
    return collection


def search_knowledge_base(
    collection: chromadb.Collection,
    disease_name: str,
    n_results: int = 2,
) -> List[dict]:
    """
    Search the knowledge base for the given disease name.

    Strategy (two-layer):
      1. Exact / substring name match — case-insensitive string check against
         every disease entry.  This guarantees "Early Blight" never resolves
         to "Late Blight" regardless of embedding cosine distances.
      2. Semantic fallback — ChromaDB vector search for queries that don't
         match any disease name exactly (e.g. free-form descriptions).

    Args:
        collection:   Initialised ChromaDB collection.
        disease_name: Disease name string (from vision module).
        n_results:    Number of top results to retrieve.

    Returns:
        List of matching disease dicts from DISEASES (may be empty).
    """
    query_lower = disease_name.lower().strip()

    # ── Layer 1: exact / substring name match ─────────────────────────────
    exact_matches: list[dict] = []
    for d in DISEASES:
        if query_lower == d["disease"].lower() or query_lower in d["disease"].lower():
            exact_matches.append(d)

    if exact_matches:
        logger.info("Exact name match for '%s' → %s", disease_name, [m['id'] for m in exact_matches])
        return exact_matches[:n_results]

    # ── Layer 2: semantic / vector search fallback ─────────────────────────
    try:
        query_embedding = _embed([disease_name])
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=min(n_results, collection.count()),
        )
    except Exception as exc:
        logger.warning("ChromaDB query failed: %s", exc)
        return []

    matched_ids: list[str] = results.get("ids", [[]])[0]
    if not matched_ids:
        return []

    id_to_disease = {d["id"]: d for d in DISEASES}
    matches: list[dict] = []
    for doc_id in matched_ids:
        if doc_id in id_to_disease:
            matches.append(id_to_disease[doc_id])

    logger.info("Semantic match for '%s' → %s", disease_name, [m['id'] for m in matches])
    return matches


def get_disease_context(disease_name: str) -> str:
    """
    High-level helper: initialise KB → search → format context string.

    Args:
        disease_name: Disease name to look up (e.g. "Early Blight").

    Returns:
        A formatted context string to inject into the Gemini prompt,
        or an empty string if nothing is found.
    """
    try:
        collection = initialize_knowledge_base()
        matches = search_knowledge_base(collection, disease_name)
    except Exception as exc:
        logger.error("RAG lookup failed for '%s': %s", disease_name, exc)
        return ""

    if not matches:
        logger.info("No RAG match found for '%s'", disease_name)
        return ""

    # Use the best (first) match for the context
    d = matches[0]

    context = (
        "VERIFIED AGRICULTURAL KNOWLEDGE:\n"
        f"Disease: {d['disease']}\n"
        f"Tamil Name: {d['tamil_name']}\n"
        f"Symptoms: {d['symptoms']}\n"
        f"Recommended Treatment: {d['treatment']}\n"
        f"Organic Alternative: {d['organic_treatment']}\n"
        f"Prevention: {d['prevention']}\n"
        f"Best Time to Spray: {d['best_time_to_spray']}\n"
        f"Products Available in India: {d['available_in_india']}\n"
        f"Approximate Cost: {d['cost']}"
    )

    logger.info("RAG context retrieved for '%s' → '%s'", disease_name, d["disease"])
    return context
