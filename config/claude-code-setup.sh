#!/usr/bin/env bash
# Manual Claude Code setup. Prefer `python -m opensearch_memory_mcp setup claude-code`,
# which also installs lifecycle hooks. This script only registers the MCP server.
set -e

claude mcp add opensearch-memory \
  --transport stdio \
  -- python -m opensearch_memory_mcp

echo "✓ opensearch-memory MCP server registered with Claude Code"
echo "  For automatic save-on-prompt/tool/stop, also run:"
echo "    python -m opensearch_memory_mcp setup claude-code"
echo "  Or add UserPromptSubmit/PostToolUse/Stop/SubagentStop hooks to ~/.claude/settings.json"
echo "  pointing at: python -m opensearch_memory_mcp hook"
