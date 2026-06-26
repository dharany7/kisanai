"""
rag.py — Knowledge base retrieval (skeleton)

Responsibilities (to be implemented in Phase 4):
  • Load the knowledge_base/ text files into ChromaDB on startup
  • Embed query strings using sentence-transformers
  • Retrieve the top-k most relevant disease/treatment chunks
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# Default path to the knowledge base directory (relative to project root)
KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parents[1] / "knowledge_base"


async def load_knowledge_base(persist_directory: str = "./chroma_db") -> None:
    """
    Parse all .txt files in the knowledge_base/ directory, chunk them, and
    upsert embeddings into a ChromaDB collection.

    Args:
        persist_directory: Local path where ChromaDB stores its data on disk.

    TODO (Phase 4):
        - Use chromadb.Client() with PersistentClient settings
        - Embed documents with sentence-transformers (e.g. all-MiniLM-L6-v2)
        - Track file checksums so we only re-embed changed files
    """
    logger.info("Loading knowledge base from %s …", KNOWLEDGE_BASE_DIR)
    raise NotImplementedError("load_knowledge_base is not yet implemented")


async def retrieve_treatment(disease_name: str, top_k: int = 3) -> List[str]:
    """
    Retrieve the most relevant treatment passages for a detected disease.

    Args:
        disease_name: Disease name returned by the vision module.
        top_k:        Number of chunks to return.

    Returns:
        List of text passages sorted by relevance (most relevant first).

    TODO (Phase 4):
        - Query ChromaDB collection using the embedded disease_name as the query
        - Return the 'documents' field from the ChromaDB query result
    """
    logger.info("Retrieving treatment info for '%s' …", disease_name)
    raise NotImplementedError("retrieve_treatment is not yet implemented")
