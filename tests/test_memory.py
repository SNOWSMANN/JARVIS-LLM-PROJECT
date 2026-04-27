import tempfile

import pytest


@pytest.fixture()
def memory_store():
    tmp = tempfile.mkdtemp()
    from jarvis.config import settings

    settings.database_url = f"sqlite:///{tmp}/test.db"
    settings.chroma_persist_dir = f"{tmp}/chroma"

    from jarvis.memory.store import MemoryStore

    m = MemoryStore()
    m.start()
    yield m


def test_conversation_and_turns(memory_store) -> None:
    cid = memory_store.start_conversation()
    memory_store.add_turn(cid, "user", "hello")
    memory_store.add_turn(cid, "assistant", "hi, Sir.")
    turns = memory_store.recent_turns(cid, n=10)
    assert [t.content for t in turns] == ["hello", "hi, Sir."]


def test_remember_and_recall(memory_store) -> None:
    mid = memory_store.remember(
        content="User loves espresso at 7am.", kind="preference", importance=0.9
    )
    assert mid >= 0
    hits = memory_store.recall("what does the user drink in the morning", n=3)
    assert hits, "recall should return at least one hit"


def test_low_importance_is_skipped(memory_store) -> None:
    mid = memory_store.remember(content="trivial", importance=0.01)
    assert mid == -1
