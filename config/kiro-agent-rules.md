# Memory Instructions for Kiro CLI

You have access to the `opensearch-memory` MCP server for persistent memory across sessions.

## Auto-save rule
After EVERY response, call `save_memory` with:
- `content`: Concise summary of what you did/said
- `role`: "assistant"
- `session_id`: Reuse the same session_id for the entire conversation
- `agent_type`: "kiro"
- `project`: Current working directory or project name
- `tags`: Relevant tags
- `tool_calls`: Any tools called

When the user sends a message, save it with `role`: "user".

## Recall
Use `recall` to search past context before complex tasks.
Use `recall_timeframe` for time-based queries.

## Analysis
Use `analyze_workflow` when asked to optimize workflow — reason over the returned
data to suggest new agents, skills, or improvements.
