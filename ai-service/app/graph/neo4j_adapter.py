from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


class Neo4jAdapter:
    def __init__(self) -> None:
        self.uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "neo4j_password")
        self.driver = None
        self.available = False
        self._connect_attempted = False

    def _connect(self) -> None:
        self._connect_attempted = True
        try:
            from neo4j import GraphDatabase

            logger.info("Neo4j connecting to %s with user=%s", self.uri, self.user)
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            self.available = True
            logger.info("Neo4j connected successfully")
        except Exception as e:
            reason = str(e).splitlines()[0] if str(e) else type(e).__name__
            logger.warning("Neo4j unavailable: %s: %s", type(e).__name__, reason)
            self.driver = None
            self.available = False

    def _ensure_connected(self) -> None:
        if not self.available and not self._connect_attempted:
            self._connect()

    @contextmanager
    def session(self):
        self._ensure_connected()
        if not self.available or not self.driver:
            yield None
            return
        s = self.driver.session()
        try:
            yield s
        finally:
            s.close()

    def run(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self._ensure_connected()
        if not self.available:
            return []
        with self.session() as s:
            if s is None:
                return []
            records = s.run(query, params or {})
            return [dict(r) for r in records]

    def run_write(self, query: str, params: dict[str, Any] | None = None) -> None:
        self._ensure_connected()
        if not self.available:
            return
        with self.session() as s:
            if s is None:
                return
            s.run(query, params or {})

    def close(self) -> None:
        if self.driver:
            self.driver.close()


neo4j_adapter = Neo4jAdapter()
