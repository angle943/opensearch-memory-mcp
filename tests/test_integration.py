"""Tests for opensearch-memory-mcp tools (requires running OpenSearch)."""

import json
import os
import time
import uuid

import pytest

# Skip entire module if no OpenSearch available
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENSEARCH_URL"), reason="OPENSEARCH_URL not set"
)


@pytest.fixture(scope="module")
def unique_prefix():
    """Use a unique index prefix so tests don't collide."""
    prefix = f"test-mem-{uuid.uuid4().hex[:8]}"
    os.environ["INDEX_PREFIX"] = prefix
    os.environ.setdefault("OPENSEARCH_VERIFY_CERTS", "false")
    yield prefix
    # Cleanup
    from opensearch_memory_mcp.server import get_client
    from opensearch_memory_mcp.config import settings

    client = get_client()
    client.indices.delete(index=f"{prefix}-*", ignore=[404])
    try:
        client.ingest.delete_pipeline(id=settings.ingest_pipeline, ignore=[404])
    except Exception:
        pass


@pytest.fixture(scope="module")
def session_id():
    return str(uuid.uuid4())


@pytest.fixture(scope="module", autouse=True)
def _setup(unique_prefix):
    """Force reload config with test prefix."""
    # Re-import to pick up new env
    import importlib
    import opensearch_memory_mcp.config as cfg_mod

    importlib.reload(cfg_mod)
    import opensearch_memory_mcp.server as srv_mod

    srv_mod.settings = cfg_mod.settings
    srv_mod._client = None  # Reset client so ensure_indices runs fresh


def test_ping():
    from opensearch_memory_mcp.server import ping

    result = json.loads(ping())
    assert "cluster_name" in result


def test_save_and_recall(session_id):
    from opensearch_memory_mcp.server import save_memory, recall

    # Save several interactions
    interactions = [
        ("I need to migrate the PostgreSQL database to version 16", "user"),
        ("I'll help you plan the PostgreSQL 16 migration. First let's check compatibility.", "assistant"),
        ("Set up JWT authentication for the REST API", "user"),
        ("Here's the JWT auth middleware implementation for Express.", "assistant"),
        ("How do I configure nginx reverse proxy?", "user"),
    ]
    for content, role in interactions:
        resp = json.loads(save_memory(content=content, role=role, session_id=session_id, agent_type="test", project="test-project"))
        assert resp["status"] == "saved"

    # Wait for indexing
    time.sleep(2)

    # Keyword recall (works without neural search)
    results = json.loads(recall(query="database migration", limit=5))
    assert len(results) > 0
    # The PostgreSQL migration interaction should be in results
    texts = [r["content"] for r in results]
    assert any("PostgreSQL" in t or "database" in t or "migration" in t for t in texts)


def test_recall_timeframe(session_id):
    from opensearch_memory_mcp.server import recall_timeframe

    results = json.loads(recall_timeframe(timeframe="today", limit=10))
    assert len(results) > 0


def test_list_sessions(session_id):
    from opensearch_memory_mcp.server import list_sessions

    sessions = json.loads(list_sessions(limit=10))
    assert len(sessions) > 0
    sids = [s["session_id"] for s in sessions]
    assert session_id in sids


def test_get_session(session_id):
    from opensearch_memory_mcp.server import get_session

    turns = json.loads(get_session(session_id=session_id))
    assert len(turns) >= 5
    # Should be ordered by timestamp
    timestamps = [t["timestamp"] for t in turns]
    assert timestamps == sorted(timestamps)


def test_analyze_usage():
    from opensearch_memory_mcp.server import analyze_usage

    result = json.loads(analyze_usage(days=1))
    assert result["total_interactions"] > 0
    assert "per_agent" in result
    assert "test" in result["per_agent"]


def test_analyze_workflow():
    from opensearch_memory_mcp.server import analyze_workflow

    result = json.loads(analyze_workflow(days=1))
    assert result["total_interactions"] > 0
    assert "frequent_topics" in result
    assert "hour_of_day_distribution" in result
