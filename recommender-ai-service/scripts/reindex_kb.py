"""
KB Reindex Script
Usage:
  python scripts/reindex_kb.py

Fetches books + reviews from services, rebuilds KB + FAISS index.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.kb_ingestion import reindex
from app.services.rag_retrieval import build_index, get_all_entries
from app.core.logging import setup_logging

setup_logging()

if __name__ == "__main__":
    print("Reindexing Knowledge Base...")
    count = reindex()
    print(f"KB entries: {count}")

    print("Building FAISS index...")
    entries = get_all_entries()
    indexed = build_index(entries)
    print(f"FAISS indexed: {indexed} vectors")
    print("Done.")
