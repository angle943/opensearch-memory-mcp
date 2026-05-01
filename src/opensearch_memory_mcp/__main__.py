"""Entry point: python -m opensearch_memory_mcp [setup kiro|claude-code]"""

import json
import sys
from pathlib import Path

STEERING_CONTENT = """\
---
inclusion: always
---
# Memory Auto-Logging

You have access to the `opensearch-memory` MCP server for persistent memory across sessions.

## Auto-save rule (MANDATORY)

After EVERY response you give, call `save_memory` with:
- `content`: A concise summary of what you did/said (not the full response — just the key action/answer)
- `role`: "assistant"
- `session_id`: Reuse the same session_id for the entire conversation. Generate one UUID at the start of each session.
- `agent_type`: "{agent_type}"
- `project`: The current working directory basename
- `tags`: Relevant tags (e.g., "bugfix", "feature", "refactor", "question")
- `tool_calls`: List any tools you called [{{name, input, output}}]

When the user sends a message, also save it:
- `content`: The user's message (abbreviated if very long)
- `role`: "user"
- Same session_id, agent_type, project

## Recall

Before starting complex tasks, use `recall` to search for relevant past context.
Use `recall_timeframe` when the user asks "what did I do yesterday?" type questions.

## Analysis

When asked to optimize workflow or suggest improvements, call `analyze_workflow`
and reason over the returned data to suggest new agents, skills, or process improvements.
"""


def _server_command() -> str:
    """Return the absolute path to the python executable running this package."""
    return str(Path(sys.executable))


def setup(agent: str) -> None:
    python_path = _server_command()

    if agent == "kiro":
        # 1. Register MCP server
        mcp_dir = Path.home() / ".kiro" / "settings"
        mcp_dir.mkdir(parents=True, exist_ok=True)
        mcp_file = mcp_dir / "mcp.json"

        server_entry = {
            "command": python_path,
            "args": ["-m", "opensearch_memory_mcp"],
        }

        if mcp_file.exists():
            existing = json.loads(mcp_file.read_text())
        else:
            existing = {"mcpServers": {}}
        existing.setdefault("mcpServers", {})["opensearch-memory"] = server_entry
        mcp_file.write_text(json.dumps(existing, indent=2) + "\n")
        print(f"✓ MCP server registered in {mcp_file}")

        # 2. Install steering file
        steering_dir = Path.home() / ".kiro" / "steering"
        steering_dir.mkdir(parents=True, exist_ok=True)
        steering_file = steering_dir / "memory-auto-logging.md"
        steering_file.write_text(STEERING_CONTENT.format(agent_type="kiro"))
        print(f"✓ Auto-logging steering file installed at {steering_file}")

    elif agent == "claude-code":
        # 1. Register MCP server
        print("Registering MCP server with Claude Code...")
        import subprocess
        result = subprocess.run(
            ["claude", "mcp", "add", "opensearch-memory", "--", python_path, "-m", "opensearch_memory_mcp"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print("✓ MCP server registered with Claude Code")
        else:
            print(f"  Could not auto-register: {result.stderr.strip()}")
            print(f"  Run manually: claude mcp add opensearch-memory -- {python_path} -m opensearch_memory_mcp")

        # 2. Install CLAUDE.md in current directory
        claude_md = Path.cwd() / "CLAUDE.md"
        content = STEERING_CONTENT.format(agent_type="claude-code")
        if claude_md.exists():
            existing = claude_md.read_text()
            if "save_memory" not in existing:
                claude_md.write_text(existing + "\n\n" + content)
                print(f"✓ Auto-logging instructions appended to {claude_md}")
            else:
                print(f"✓ {claude_md} already has memory instructions")
        else:
            claude_md.write_text(content)
            print(f"✓ Auto-logging instructions written to {claude_md}")

    else:
        print(f"Unknown agent: {agent}. Use 'kiro' or 'claude-code'.")
        sys.exit(1)

    print("\n✓ Setup complete. All new sessions will auto-log to OpenSearch.")
    print("  Config: ~/.opensearch-memory/config.json")


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "setup":
        setup(sys.argv[2])
    else:
        from .server import mcp
        mcp.run(transport="stdio")


main()
