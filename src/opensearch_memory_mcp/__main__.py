"""Entry point: python -m opensearch_memory_mcp [setup kiro|claude-code | hook]"""

import json
import sys
from pathlib import Path

# CLAUDE.md content for Kiro (still prompt-based — Kiro doesn't have hooks).
KIRO_STEERING = """\
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
- `agent_type`: "kiro"
- `project`: The current working directory basename
- `tags`: Relevant tags (e.g., "bugfix", "feature", "refactor", "question")
- `tool_calls`: List any tools you called [{name, input, output}]

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

# CLAUDE.md content for Claude Code. Saves are handled by lifecycle hooks
# (UserPromptSubmit / PostToolUse / Stop), so the model only needs guidance
# on when to recall and analyze.
CLAUDE_CODE_STEERING = """\
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
"""


def _server_command() -> str:
    """Absolute path to the python executable running this package."""
    return str(Path(sys.executable))


def _install_claude_hooks(python_path: str) -> Path:
    """Add UserPromptSubmit / PostToolUse / Stop hooks to ~/.claude/settings.json."""
    settings_dir = Path.home() / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    settings_file = settings_dir / "settings.json"

    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text() or "{}")
        except json.JSONDecodeError:
            print(f"  ⚠ {settings_file} is not valid JSON; refusing to overwrite.")
            print(f"     Add the hooks block manually (see README).")
            return settings_file
    else:
        settings = {}

    command = f"{python_path} -m opensearch_memory_mcp hook"
    hook_entry = {"type": "command", "command": command}

    hooks = settings.setdefault("hooks", {})
    for event in ("UserPromptSubmit", "PostToolUse", "Stop", "SubagentStop"):
        matchers = hooks.setdefault(event, [])
        # Idempotent: skip if our command is already registered for this event.
        already = any(
            any(h.get("command") == command for h in (m.get("hooks") or []))
            for m in matchers
            if isinstance(m, dict)
        )
        if already:
            continue
        # PostToolUse uses a matcher (regex over tool name); the others don't.
        if event == "PostToolUse":
            matchers.append({"matcher": ".*", "hooks": [hook_entry]})
        else:
            matchers.append({"hooks": [hook_entry]})

    settings_file.write_text(json.dumps(settings, indent=2) + "\n")
    return settings_file


def setup(agent: str) -> None:
    python_path = _server_command()

    if agent == "kiro":
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

        steering_dir = Path.home() / ".kiro" / "steering"
        steering_dir.mkdir(parents=True, exist_ok=True)
        steering_file = steering_dir / "memory-auto-logging.md"
        steering_file.write_text(KIRO_STEERING)
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

        # 2. Install lifecycle hooks
        settings_file = _install_claude_hooks(python_path)
        print(f"✓ Lifecycle hooks installed in {settings_file}")
        print("    UserPromptSubmit → save user prompts")
        print("    PostToolUse      → save tool calls")
        print("    Stop / SubagentStop → save assistant replies")

        # 3. Install CLAUDE.md (recall/analyze guidance only — saves are automatic)
        claude_md = Path.cwd() / "CLAUDE.md"
        content = CLAUDE_CODE_STEERING
        if claude_md.exists():
            existing = claude_md.read_text()
            if "opensearch-memory" not in existing:
                claude_md.write_text(existing + "\n\n" + content)
                print(f"✓ Memory guidance appended to {claude_md}")
            else:
                print(f"✓ {claude_md} already references opensearch-memory")
        else:
            claude_md.write_text(content)
            print(f"✓ Memory guidance written to {claude_md}")

    else:
        print(f"Unknown agent: {agent}. Use 'kiro' or 'claude-code'.")
        sys.exit(1)

    print("\n✓ Setup complete.")
    print("  Config: ~/.opensearch-memory/config.json")


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == "hook":
        from .hook import main as hook_main
        hook_main()
        return
    if len(sys.argv) >= 3 and sys.argv[1] == "setup":
        setup(sys.argv[2])
        return
    from .server import mcp
    mcp.run(transport="stdio")


main()
