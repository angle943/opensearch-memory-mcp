# Memory

This project has the `opensearch-memory` MCP server registered. User prompts,
tool calls, and assistant replies are persisted automatically by Claude Code
lifecycle hooks — you do NOT need to call `save_memory` yourself.

## Recall

Before starting complex tasks, call `recall` to search past sessions for
relevant context. Use `recall_timeframe` for questions like "what did I do
yesterday?".

## Analysis

When asked to optimize workflow or suggest improvements, call `analyze_workflow`
and reason over the returned data to suggest new agents, skills, or process
improvements.
