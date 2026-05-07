# Memory Instructions for Claude Code

The `opensearch-memory` MCP server is registered for this project. User
prompts, tool calls, and assistant replies are persisted automatically by
Claude Code lifecycle hooks (`UserPromptSubmit`, `PostToolUse`, `Stop`,
`SubagentStop`) — you do **not** need to call `save_memory` yourself.

## Recall

Before starting complex tasks, call `recall` to search past sessions for
relevant context. Use `recall_timeframe` for questions like "what did I do
yesterday?".

## Analysis

When asked to optimize workflow, call `analyze_workflow` and reason over
the results to suggest new agents, skills, or process improvements.
