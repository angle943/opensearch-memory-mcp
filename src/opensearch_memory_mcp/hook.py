"""Claude Code lifecycle hook driver.

Reads a single JSON payload on stdin (as defined by Claude Code's hooks API)
and writes the relevant interaction to OpenSearch via `save_memory`.

Wired up as `command: <python> -m opensearch_memory_mcp hook` in
`~/.claude/settings.json` for these events:

    UserPromptSubmit  -> persist the user's prompt
    PostToolUse       -> persist a tool call (name + input + output)
    Stop / SubagentStop -> persist the assistant's final text reply
                          (read from the JSONL transcript)

Hook failures must never block Claude, so all errors are swallowed and the
process always exits 0.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_TRUNCATE = 4000
_ASSISTANT_TRUNCATE = 8000


def _project_name(cwd: str) -> str:
    return Path(cwd).name if cwd else ""


def _last_assistant_text(transcript_path: str) -> str:
    """Return the text of the most recent assistant turn from a JSONL transcript."""
    if not transcript_path:
        return ""
    p = Path(transcript_path)
    if not p.exists():
        return ""
    try:
        lines = p.read_text().splitlines()
    except Exception:
        return ""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        msg = entry.get("message") or {}
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, list):
            text = "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
        elif isinstance(content, str):
            text = content.strip()
        else:
            text = ""
        if text:
            return text
    return ""


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + "…"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    event = payload.get("hook_event_name", "")
    session_id = payload.get("session_id", "") or ""
    project = _project_name(payload.get("cwd", "") or "")

    # Imported lazily so a misconfigured cluster doesn't crash the hook before
    # it can swallow the error.
    try:
        from .server import save_memory_impl as save_memory
    except Exception as e:
        print(f"opensearch-memory hook: import failed: {e}", file=sys.stderr)
        sys.exit(0)

    try:
        if event == "UserPromptSubmit":
            prompt = payload.get("prompt", "") or ""
            if prompt.strip():
                save_memory(
                    content=prompt,
                    role="user",
                    session_id=session_id,
                    agent_type="claude-code",
                    project=project,
                )
        elif event == "PostToolUse":
            tool_name = payload.get("tool_name", "") or ""
            # Don't recursively log our own writes.
            if tool_name in ("save_memory", "mcp__opensearch-memory__save_memory"):
                sys.exit(0)
            tool_input = payload.get("tool_input", {})
            tool_response = payload.get("tool_response", {})
            save_memory(
                content=f"Used {tool_name}",
                role="assistant",
                session_id=session_id,
                agent_type="claude-code",
                project=project,
                tool_calls=[
                    {
                        "name": tool_name,
                        "input": _truncate(json.dumps(tool_input, default=str), _TRUNCATE),
                        "output": _truncate(json.dumps(tool_response, default=str), _TRUNCATE),
                    }
                ],
            )
        elif event in ("Stop", "SubagentStop"):
            text = _last_assistant_text(payload.get("transcript_path", "") or "")
            if text:
                save_memory(
                    content=_truncate(text, _ASSISTANT_TRUNCATE),
                    role="assistant",
                    session_id=session_id,
                    agent_type="claude-code",
                    project=project,
                )
    except Exception as e:
        print(f"opensearch-memory hook: save failed: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
