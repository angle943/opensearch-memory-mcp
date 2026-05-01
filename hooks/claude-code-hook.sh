#!/usr/bin/env bash
# Claude Code PostToolUse hook — auto-saves tool interactions to memory
# Install: copy to .claude/hooks/PostToolUse.sh or configure in settings
#
# This hook is called after every tool use. It sends a save_memory call
# to capture the tool interaction automatically.

# The hook receives tool info via environment variables from Claude Code:
# TOOL_NAME, TOOL_INPUT, TOOL_OUTPUT, SESSION_ID

if [ -z "$TOOL_NAME" ] || [ "$TOOL_NAME" = "save_memory" ]; then
  exit 0  # Don't recursively save save_memory calls
fi

# Use the MCP server's save_memory tool via Claude Code's internal mechanism
# This is a placeholder — actual hook integration depends on Claude Code's
# hook API which passes tool context automatically.
echo "Memory hook: captured $TOOL_NAME" >&2
