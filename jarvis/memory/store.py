"""Unified persistent memory for Jarvis.

Combines:
- SQL (SQLAlchemy) for structured history, audit, and ranked 'facts'
- Chroma vector store for semantic recall

Design goals:
- Short-term (last N turns) handled in-process by the orchestrator.
- Long-term facts stored here with importance ranking + decay.
- Semantic recall: vector search over facts + past assistant/user turns.
- Everything local-first (SQLite + on-disk Chroma). Swap to Postgres by
  changing DATABASE_URL.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, desc, select
from sqlalchemy.orm import Session, sessionmaker

from jarvis.config import settings
from jarvis.memory.models import AuditEvent, Base, Conversation, Memory, Turn
from jarvis.observability import get_logger

log = get_logger(__name__)


class MemoryStore:
    """Persistent memory facade."""

    def __init__(self) -> None:
        self._sql_engine = None
        self._SessionLocal: sessionmaker[Session] | None = None
        self._chroma_client = None
        self._chroma_collection = None
        self._current_conversation_id: int | None = None

    # ---------- lifecycle ----------

    def start(self) -> None:
        """Initialize SQL + Chroma. Safe to call multiple times."""
        if self._sql_engine is not None:
            return

        Path("data").mkdir(parents=True, exist_ok=True)

        self._sql_engine = create_engine(
            settings.database_url,
            echo=False,
            future=True,
            connect_args=(
                {"check_same_thread": False}
                if settings.database_url.startswith("sqlite")
                else {}
            ),
        )
        Base.metadata.create_all(self._sql_engine)
        self._SessionLocal = sessionmaker(
            bind=self._sql_engine, autoflush=False, expire_on_commit=False, future=True
        )

        # Chroma — optional at import time, lazy on first use.
        try:
            import chromadb

            Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"hnsw:space": "cosine"},
            )
            log.info("Chroma vector store ready at {}", settings.chroma_persist_dir)
        except Exception as e:  # noqa: BLE001
            log.warning("Chroma unavailable, vector recall disabled: {}", e)
            self._chroma_client = None
            self._chroma_collection = None

        log.info("Memory store initialized ({})", settings.database_url)

    def session(self) -> Session:
        assert self._SessionLocal is not None, "MemoryStore not started"
        return self._SessionLocal()

    # ---------- conversations ----------

    def start_conversation(self) -> int:
        with self.session() as s:
            conv = Conversation()
            s.add(conv)
            s.commit()
            s.refresh(conv)
            self._current_conversation_id = conv.id
            log.info("Conversation #{} started", conv.id)
            return conv.id

    def end_conversation(self, conversation_id: int, summary: str | None = None) -> None:
        with self.session() as s:
            conv = s.get(Conversation, conversation_id)
            if conv is None:
                return
            conv.ended_at = datetime.utcnow()
            if summary:
                conv.summary = summary
            s.commit()

    def add_turn(
        self,
        conversation_id: int,
        role: str,
        content: str,
        extra: dict[str, Any] | None = None,
    ) -> int:
        with self.session() as s:
            turn = Turn(
                conversation_id=conversation_id,
                role=role,
                content=content,
                extra=extra or {},
            )
            s.add(turn)
            s.commit()
            s.refresh(turn)

        # Mirror into vector store for semantic recall (user + assistant turns only).
        if role in {"user", "assistant"} and content.strip():
            self._vector_add(
                id_=f"turn-{turn.id}",
                text=content,
                metadata={
                    "type": "turn",
                    "role": role,
                    "conversation_id": conversation_id,
                    "turn_id": turn.id,
                },
            )
        return turn.id

    def recent_turns(self, conversation_id: int, n: int = 20) -> list[Turn]:
        with self.session() as s:
            stmt = (
                select(Turn)
                .where(Turn.conversation_id == conversation_id)
                .order_by(desc(Turn.created_at))
                .limit(n)
            )
            turns = list(s.scalars(stmt).all())
            turns.reverse()
            return turns

    # ---------- long-term memories ----------

    def remember(
        self,
        content: str,
        kind: str = "fact",
        importance: float = 0.5,
        source: str = "conversation",
        subject: str = "user",
        extra: dict[str, Any] | None = None,
    ) -> int:
        """Store a durable memory."""
        if importance < settings.memory_importance_threshold:
            log.debug("Skipping low-importance memory ({:.2f}): {}", importance, content[:60])
            return -1

        with self.session() as s:
            m = Memory(
                kind=kind,
                content=content,
                importance=importance,
                source=source,
                subject=subject,
                extra=extra or {},
            )
            s.add(m)
            s.commit()
            s.refresh(m)

        self._vector_add(
            id_=f"mem-{m.id}",
            text=content,
            metadata={
                "type": "memory",
                "kind": kind,
                "importance": importance,
                "memory_id": m.id,
                "subject": subject,
            },
        )
        log.info("Remembered [{}/{:.2f}]: {}", kind, importance, content[:80])
        return m.id

    def recall(self, query: str, n: int = 5) -> list[dict[str, Any]]:
        """Semantic recall across memories + past turns."""
        if self._chroma_collection is None:
            return self._recall_sql_fallback(query, n)

        try:
            res = self._chroma_collection.query(
                query_texts=[query],
                n_results=max(n * 2, 10),
            )
        except Exception as e:  # noqa: BLE001
            log.warning("Chroma query failed: {}", e)
            return self._recall_sql_fallback(query, n)

        out: list[dict[str, Any]] = []
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for i, doc_id in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            out.append(
                {
                    "id": doc_id,
                    "text": docs[i] if i < len(docs) else "",
                    "metadata": meta,
                    "distance": dists[i] if i < len(dists) else None,
                }
            )
        # Mark memory hits as recalled for importance decay / boosting later.
        mem_ids = [
            m["metadata"].get("memory_id")
            for m in out
            if m.get("metadata", {}).get("type") == "memory"
        ]
        if mem_ids:
            self._bump_recall(mem_ids)
        return out[:n]

    def _recall_sql_fallback(self, query: str, n: int) -> list[dict[str, Any]]:
        """LIKE-based fallback when vector store is unavailable."""
        with self.session() as s:
            stmt = (
                select(Memory)
                .where(Memory.content.contains(query))
                .order_by(desc(Memory.importance))
                .limit(n)
            )
            return [
                {
                    "id": f"mem-{m.id}",
                    "text": m.content,
                    "metadata": {"type": "memory", "kind": m.kind, "importance": m.importance},
                    "distance": None,
                }
                for m in s.scalars(stmt).all()
            ]

    def _bump_recall(self, memory_ids: list[int]) -> None:
        with self.session() as s:
            for mid in memory_ids:
                if mid is None:
                    continue
                m = s.get(Memory, mid)
                if m is None:
                    continue
                m.recall_count += 1
                m.last_recalled_at = datetime.utcnow()
                m.importance = min(1.0, m.importance + 0.01)
            s.commit()

    def forget(self, memory_id: int) -> None:
        with self.session() as s:
            m = s.get(Memory, memory_id)
            if m is not None:
                s.delete(m)
                s.commit()
        if self._chroma_collection is not None:
            import contextlib

            with contextlib.suppress(Exception):
                self._chroma_collection.delete(ids=[f"mem-{memory_id}"])

    # ---------- audit ----------

    def audit(
        self,
        action: str,
        target: str = "",
        ok: bool = True,
        detail: dict[str, Any] | None = None,
        actor: str = "jarvis",
    ) -> None:
        with self.session() as s:
            s.add(
                AuditEvent(
                    action=action,
                    target=target,
                    ok=ok,
                    detail=detail or {},
                    actor=actor,
                )
            )
            s.commit()
        log.bind(audit=True).info(
            "AUDIT actor={} action={} target={} ok={} detail={}",
            actor,
            action,
            target,
            ok,
            detail,
        )

    # ---------- vector helpers ----------

    def _vector_add(self, id_: str, text: str, metadata: dict[str, Any]) -> None:
        if self._chroma_collection is None or not text.strip():
            return
        try:
            # Chroma 0.5 metadata values must be primitive
            safe_meta = {k: v for k, v in metadata.items() if isinstance(v, (str, int, float, bool))}
            self._chroma_collection.add(
                ids=[id_ or str(uuid.uuid4())],
                documents=[text],
                metadatas=[safe_meta],
            )
        except Exception as e:  # noqa: BLE001
            log.warning("Chroma add failed: {}", e)
