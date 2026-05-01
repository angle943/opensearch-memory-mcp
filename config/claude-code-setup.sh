#!/usr/bin/env bash
# Register opensearch-memory MCP server with Claude Code
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

claude mcp add opensearch-memory \
  --transport stdio \
  -- python -m opensearch_memory_mcp

echo "✓ opensearch-memory MCP server registered with Claude Code"
echo "  Set env vars: OPENSEARCH_URL, OPENSEARCH_USER, OPENSEARCH_PASSWORD, OPENSEARCH_MODEL_ID"
