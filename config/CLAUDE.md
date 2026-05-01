# Memory Instructions for Claude Code

You have access to the `opensearch-memory` MCP server for persistent memory across sessions.

## Auto-save rule
After EVERY response you give to the user, call `save_memory` with:
- `content`: A concise summary of what you did/said
- `role`: "assistant"
- `session_id`: Reuse the same session_id for the entire conversation
- `agent_type`: "claude-code"
- `project`: The current working directory or project name
- `tags`: Relevant tags (e.g., "bugfix", "feature", "refactor")
- `tool_calls`: List any tools you called [{name, input, output}]

When the user sends a message, also save it:
- `content`: The user's message
- `role`: "user"

## Recall
Before starting complex tasks, use `recall` to search for relevant past context.
Use `recall_timeframe` when the user asks "what did I do yesterday?" type questions.

## Analysis
When asked to optimize workflow, call `analyze_workflow` and reason over the results
to suggest new agents, skills, or process improvements.
