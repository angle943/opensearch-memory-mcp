"""OpenSearch index and pipeline management."""

import logging
from opensearchpy import OpenSearch

from .config import settings

log = logging.getLogger(__name__)


def _interactions_mappings() -> dict:
    mapping: dict = {
        "properties": {
            "session_id": {"type": "keyword"},
            "agent_type": {"type": "keyword"},
            "timestamp": {"type": "date"},
            "role": {"type": "keyword"},
            "content": {"type": "text"},
            "content_text": {"type": "text"},
            "tool_calls": {
                "type": "nested",
                "properties": {
                    "name": {"type": "keyword"},
                    "input": {"type": "text"},
                    "output": {"type": "text"},
                },
            },
            "project": {"type": "keyword"},
            "tags": {"type": "keyword"},
        }
    }
    if settings.opensearch_model_id:
        mapping["properties"]["content_embedding"] = {
            "type": "knn_vector",
            "dimension": settings.embedding_dimension,
            "method": {"engine": "lucene", "space_type": "l2", "name": "hnsw"},
        }
    return mapping


def _sessions_mappings() -> dict:
    return {
        "properties": {
            "session_id": {"type": "keyword"},
            "agent_type": {"type": "keyword"},
            "started_at": {"type": "date"},
            "last_active": {"type": "date"},
            "project": {"type": "keyword"},
            "summary": {"type": "text"},
            "turn_count": {"type": "integer"},
        }
    }


def ensure_indices(client: OpenSearch) -> None:
    """Idempotently create indices and pipelines."""
    # Ingest pipeline (only if model configured)
    if settings.opensearch_model_id:
        if not client.ingest.get_pipeline(id=settings.ingest_pipeline, ignore=404):
            client.ingest.put_pipeline(
                id=settings.ingest_pipeline,
                body={
                    "description": "Embedding pipeline for memory interactions",
                    "processors": [
                        {
                            "text_embedding": {
                                "model_id": settings.opensearch_model_id,
                                "field_map": {"content_text": "content_embedding"},
                            }
                        }
                    ],
                },
            )
            log.info("Created ingest pipeline %s", settings.ingest_pipeline)

        # Search pipeline for hybrid search
        try:
            client.transport.perform_request("GET", f"/_search/pipeline/{settings.search_pipeline}")
        except Exception:
            client.transport.perform_request(
                "PUT",
                f"/_search/pipeline/{settings.search_pipeline}",
                body={
                    "description": "Hybrid search normalization",
                    "phase_results_processors": [
                        {
                            "normalization-processor": {
                                "normalization": {"technique": "min_max"},
                                "combination": {
                                    "technique": "arithmetic_mean",
                                    "parameters": {"weights": [0.7, 0.3]},
                                },
                            }
                        }
                    ],
                },
            )
            log.info("Created search pipeline %s", settings.search_pipeline)

    # Interactions index
    idx = settings.interactions_index
    if not client.indices.exists(index=idx):
        index_settings: dict = {"index.knn": True} if settings.opensearch_model_id else {}
        if settings.opensearch_model_id:
            index_settings["default_pipeline"] = settings.ingest_pipeline
        client.indices.create(
            index=idx,
            body={"settings": index_settings, "mappings": _interactions_mappings()},
        )
        log.info("Created index %s", idx)

    # Sessions index
    sidx = settings.sessions_index
    if not client.indices.exists(index=sidx):
        client.indices.create(index=sidx, body={"mappings": _sessions_mappings()})
        log.info("Created index %s", sidx)
