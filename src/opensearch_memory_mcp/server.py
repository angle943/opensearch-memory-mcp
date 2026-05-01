"""MCP server with all memory tools."""

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP
from opensearchpy import OpenSearch

from .config import settings
from .opensearch_manager import ensure_indices

log = logging.getLogger(__name__)
mcp = FastMCP("opensearch-memory")

_client: OpenSearch | None = None


def get_client() -> OpenSearch:
    global _client
    if _client is None:
        kwargs: dict = {
            "hosts": [settings.opensearch_url],
            "verify_certs": settings.opensearch_verify_certs,
            "ssl_show_warn": False,
        }
        if settings.http_auth:
            kwargs["http_auth"] = settings.http_auth
        _client = OpenSearch(**kwargs)
        ensure_indices(_client)
    return _client


# ---------------------------------------------------------------------------
# Tool: ping
# ---------------------------------------------------------------------------

@mcp.tool()
def ping() -> str:
    """Check OpenSearch connectivity and return cluster health."""
    try:
        info = get_client().cluster.health()
        return json.dumps(info, indent=2)
    except Exception as e:
        return f"Connection failed: {e}"


# ---------------------------------------------------------------------------
# Tool: save_memory
# ---------------------------------------------------------------------------

@mcp.tool()
def save_memory(
    content: str,
    role: str = "assistant",
    session_id: str = "",
    agent_type: str = "unknown",
    project: str = "",
    tags: list[str] | None = None,
    tool_calls: list[dict] | None = None,
) -> str:
    """Save a conversation turn to persistent memory.

    Args:
        content: The interaction text (user message or agent response).
        role: 'user' or 'assistant'.
        session_id: Session identifier. Auto-generated if empty.
        agent_type: Agent name (e.g. 'kiro', 'claude-code').
        project: Project/workspace context.
        tags: Optional tags for categorization.
        tool_calls: Optional list of tool calls [{name, input, output}].
    """
    client = get_client()
    if not session_id:
        session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Build combined text for embedding
    parts = [f"[{role}] {content}"]
    for tc in tool_calls or []:
        parts.append(f"[tool:{tc.get('name','')}] {tc.get('input','')} -> {tc.get('output','')}")
    content_text = "\n".join(parts)

    doc = {
        "session_id": session_id,
        "agent_type": agent_type,
        "timestamp": now,
        "role": role,
        "content": content,
        "content_text": content_text,
        "project": project,
        "tags": tags or [],
        "tool_calls": tool_calls or [],
    }

    resp = client.index(index=settings.interactions_index, body=doc)

    # Upsert session
    client.update(
        index=settings.sessions_index,
        id=session_id,
        body={
            "script": {
                "source": "ctx._source.last_active = params.now; ctx._source.turn_count += 1",
                "params": {"now": now},
            },
            "upsert": {
                "session_id": session_id,
                "agent_type": agent_type,
                "started_at": now,
                "last_active": now,
                "project": project,
                "summary": "",
                "turn_count": 1,
            },
        },
    )

    return json.dumps({"status": "saved", "id": resp["_id"], "session_id": session_id})


# ---------------------------------------------------------------------------
# Tool: recall — hybrid semantic + keyword search
# ---------------------------------------------------------------------------

@mcp.tool()
def recall(
    query: str,
    limit: int = 10,
    agent_type: str = "",
    project: str = "",
    session_id: str = "",
) -> str:
    """Search past interactions by meaning (semantic + keyword hybrid search).

    Args:
        query: Natural language search query.
        limit: Max results to return.
        agent_type: Filter by agent.
        project: Filter by project.
        session_id: Filter by session.
    """
    client = get_client()
    filters = _build_filters(agent_type, project, session_id)

    if settings.opensearch_model_id:
        # Hybrid search
        body: dict = {
            "size": limit,
            "_source": {"excludes": ["content_embedding"]},
            "query": {
                "hybrid": {
                    "queries": [
                        {"neural": {"content_embedding": {"query_text": query, "model_id": settings.opensearch_model_id, "k": limit}}},
                        {"match": {"content_text": {"query": query}}},
                    ]
                }
            },
        }
        if filters:
            body["query"] = {"bool": {"must": [body["query"]], "filter": filters}}
        params = {"search_pipeline": settings.search_pipeline}
    else:
        # Keyword-only fallback
        match_q: dict = {"match": {"content_text": {"query": query}}}
        body = {
            "size": limit,
            "_source": {"excludes": ["content_embedding"]},
            "query": {"bool": {"must": [match_q], "filter": filters}} if filters else match_q,
        }
        params = {}

    resp = client.search(index=settings.interactions_index, body=body, params=params)
    return _format_hits(resp)


# ---------------------------------------------------------------------------
# Tool: recall_timeframe
# ---------------------------------------------------------------------------

def _parse_timeframe(tf: str) -> tuple[str, str]:
    """Parse natural language timeframe into (gte, lte) ISO strings."""
    now = datetime.now(timezone.utc)
    lte = now.isoformat()

    if tf.lower() == "today":
        gte = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    elif tf.lower() == "yesterday":
        y = now - timedelta(days=1)
        gte = y.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        lte = y.replace(hour=23, minute=59, second=59).isoformat()
    elif m := re.match(r"last\s+(\d+)\s+(day|hour|week|minute)s?", tf.lower()):
        n, unit = int(m.group(1)), m.group(2)
        delta = {"day": timedelta(days=n), "hour": timedelta(hours=n), "week": timedelta(weeks=n), "minute": timedelta(minutes=n)}
        gte = (now - delta[unit]).isoformat()
    else:
        # Assume ISO date or date range
        gte = tf
        if "/" in tf:
            parts = tf.split("/")
            gte, lte = parts[0], parts[1]
    return gte, lte


@mcp.tool()
def recall_timeframe(
    timeframe: str,
    query: str = "",
    agent_type: str = "",
    project: str = "",
    limit: int = 20,
) -> str:
    """Retrieve interactions within a time window.

    Args:
        timeframe: Time expression — 'today', 'yesterday', 'last 3 days', 'last 2 hours', or ISO date.
        query: Optional semantic search within the timeframe.
        agent_type: Filter by agent.
        project: Filter by project.
        limit: Max results.
    """
    client = get_client()
    gte, lte = _parse_timeframe(timeframe)
    time_filter = {"range": {"timestamp": {"gte": gte, "lte": lte}}}
    filters = [time_filter] + _build_filters(agent_type, project)

    if query and settings.opensearch_model_id:
        body: dict = {
            "size": limit,
            "_source": {"excludes": ["content_embedding"]},
            "query": {
                "bool": {
                    "must": [
                        {"hybrid": {"queries": [
                            {"neural": {"content_embedding": {"query_text": query, "model_id": settings.opensearch_model_id, "k": limit}}},
                            {"match": {"content_text": {"query": query}}},
                        ]}}
                    ],
                    "filter": filters,
                }
            },
        }
        params = {"search_pipeline": settings.search_pipeline}
    elif query:
        body = {
            "size": limit,
            "_source": {"excludes": ["content_embedding"]},
            "query": {"bool": {"must": [{"match": {"content_text": query}}], "filter": filters}},
        }
        params = {}
    else:
        body = {
            "size": limit,
            "_source": {"excludes": ["content_embedding"]},
            "query": {"bool": {"filter": filters}},
            "sort": [{"timestamp": "desc"}],
        }
        params = {}

    resp = client.search(index=settings.interactions_index, body=body, params=params)
    return _format_hits(resp)


# ---------------------------------------------------------------------------
# Tool: list_sessions
# ---------------------------------------------------------------------------

@mcp.tool()
def list_sessions(
    agent_type: str = "",
    project: str = "",
    limit: int = 20,
    days: int = 0,
) -> str:
    """List recent memory sessions.

    Args:
        agent_type: Filter by agent.
        project: Filter by project.
        limit: Max sessions to return.
        days: Only sessions from last N days (0 = all).
    """
    client = get_client()
    filters = _build_filters(agent_type, project)
    if days > 0:
        gte = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        filters.append({"range": {"last_active": {"gte": gte}}})

    q: dict = {"bool": {"filter": filters}} if filters else {"match_all": {}}
    body = {"size": limit, "query": q, "sort": [{"last_active": "desc"}]}
    resp = client.search(index=settings.sessions_index, body=body)
    sessions = [hit["_source"] for hit in resp["hits"]["hits"]]
    return json.dumps(sessions, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: get_session
# ---------------------------------------------------------------------------

@mcp.tool()
def get_session(session_id: str) -> str:
    """Get the full conversation history for a session.

    Args:
        session_id: The session identifier.
    """
    client = get_client()
    body = {
        "size": 200,
        "_source": {"excludes": ["content_embedding", "content_text"]},
        "query": {"term": {"session_id": session_id}},
        "sort": [{"timestamp": "asc"}],
    }
    resp = client.search(index=settings.interactions_index, body=body)
    turns = [hit["_source"] for hit in resp["hits"]["hits"]]
    return json.dumps(turns, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: analyze_usage
# ---------------------------------------------------------------------------

@mcp.tool()
def analyze_usage(days: int = 7, agent_type: str = "") -> str:
    """Return usage analytics for the agent to reason over.

    Args:
        days: Number of days to analyze.
        agent_type: Filter by agent.
    """
    client = get_client()
    gte = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    filters: list[dict] = [{"range": {"timestamp": {"gte": gte}}}]
    if agent_type:
        filters.append({"term": {"agent_type": agent_type}})

    body = {
        "size": 0,
        "query": {"bool": {"filter": filters}},
        "aggs": {
            "per_day": {"date_histogram": {"field": "timestamp", "calendar_interval": "day"}},
            "per_agent": {"terms": {"field": "agent_type", "size": 20}},
            "per_project": {"terms": {"field": "project", "size": 20}},
            "top_sessions": {"terms": {"field": "session_id", "size": 10, "order": {"_count": "desc"}}},
            "tool_names": {
                "nested": {"path": "tool_calls"},
                "aggs": {"names": {"terms": {"field": "tool_calls.name", "size": 20}}},
            },
        },
    }
    resp = client.search(index=settings.interactions_index, body=body)
    aggs = resp["aggregations"]
    result = {
        "total_interactions": resp["hits"]["total"]["value"],
        "per_day": [{b["key_as_string"]: b["doc_count"]} for b in aggs["per_day"]["buckets"]],
        "per_agent": {b["key"]: b["doc_count"] for b in aggs["per_agent"]["buckets"]},
        "per_project": {b["key"]: b["doc_count"] for b in aggs["per_project"]["buckets"]},
        "top_sessions": {b["key"]: b["doc_count"] for b in aggs["top_sessions"]["buckets"]},
        "top_tools": {b["key"]: b["doc_count"] for b in aggs["tool_names"]["names"]["buckets"]},
    }
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Tool: analyze_workflow
# ---------------------------------------------------------------------------

@mcp.tool()
def analyze_workflow(days: int = 7, project: str = "") -> str:
    """Return workflow analytics — topics, patterns, tool usage, time distribution.

    The calling agent should use this data to suggest workflow optimizations,
    new agents, or skills.

    Args:
        days: Number of days to analyze.
        project: Filter by project.
    """
    client = get_client()
    gte = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    filters: list[dict] = [{"range": {"timestamp": {"gte": gte}}}]
    if project:
        filters.append({"term": {"project": project}})

    body = {
        "size": 0,
        "query": {"bool": {"filter": filters}},
        "aggs": {
            "frequent_topics": {"significant_terms": {"field": "content_text", "size": 20}},
            "hourly_distribution": {"date_histogram": {"field": "timestamp", "calendar_interval": "hour"}},
            "per_role": {"terms": {"field": "role"}},
            "tool_names": {
                "nested": {"path": "tool_calls"},
                "aggs": {"names": {"terms": {"field": "tool_calls.name", "size": 30}}},
            },
            "sessions_summary": {
                "terms": {"field": "session_id", "size": 20, "order": {"_count": "desc"}},
                "aggs": {"projects": {"terms": {"field": "project", "size": 5}}},
            },
        },
    }
    resp = client.search(index=settings.interactions_index, body=body)
    aggs = resp["aggregations"]

    # Collapse hourly into hour-of-day buckets
    hour_counts: dict[int, int] = {}
    for b in aggs["hourly_distribution"]["buckets"]:
        h = datetime.fromisoformat(b["key_as_string"].replace("Z", "+00:00")).hour
        hour_counts[h] = hour_counts.get(h, 0) + b["doc_count"]

    result = {
        "total_interactions": resp["hits"]["total"]["value"],
        "frequent_topics": [{"term": b["key"], "score": b["score"], "count": b["doc_count"]} for b in aggs["frequent_topics"]["buckets"]],
        "hour_of_day_distribution": hour_counts,
        "role_breakdown": {b["key"]: b["doc_count"] for b in aggs["per_role"]["buckets"]},
        "top_tools": {b["key"]: b["doc_count"] for b in aggs["tool_names"]["names"]["buckets"]},
        "active_sessions": [
            {"session_id": b["key"], "turns": b["doc_count"], "projects": [p["key"] for p in b["projects"]["buckets"]]}
            for b in aggs["sessions_summary"]["buckets"]
        ],
    }
    return json.dumps(result, indent=2, default=str)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_filters(agent_type: str = "", project: str = "", session_id: str = "") -> list[dict]:
    f: list[dict] = []
    if agent_type:
        f.append({"term": {"agent_type": agent_type}})
    if project:
        f.append({"term": {"project": project}})
    if session_id:
        f.append({"term": {"session_id": session_id}})
    return f


def _format_hits(resp: dict) -> str:
    results = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        src.pop("content_embedding", None)
        src.pop("content_text", None)
        src["_score"] = hit.get("_score")
        results.append(src)
    return json.dumps(results, indent=2, default=str)
