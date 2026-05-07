#!/usr/bin/env bash
# Claude Code lifecycle hook driver — auto-saves prompts, tool calls, and
# assistant replies to OpenSearch.
#
# `python -m opensearch_memory_mcp setup claude-code` installs this for you
# by registering `python -m opensearch_memory_mcp hook` directly in
# ~/.claude/settings.json. This script is provided as a convenience for
# users who want to wire the hook in by hand.
#
# Wire in by adding to ~/.claude/settings.json:
#   {
#     "hooks": {
#       "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "/abs/path/to/this/script"}]}],
#       "PostToolUse":      [{"matcher": ".*", "hooks": [{"type": "command", "command": "/abs/path/to/this/script"}]}],
#       "Stop":             [{"hooks": [{"type": "command", "command": "/abs/path/to/this/script"}]}],
#       "SubagentStop":     [{"hooks": [{"type": "command", "command": "/abs/path/to/this/script"}]}]
#     }
#   }
#
# Claude passes the hook payload as JSON on stdin; we forward it as-is.
# Errors are swallowed by the Python driver so a broken cluster never blocks Claude.

exec python3 -m opensearch_memory_mcp hook
