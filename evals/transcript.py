"""Turn an agent response stream into something that can be scored."""
from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class Transcript:
    text: str = ""
    tools: list[str] = field(default_factory=list)
    error: str | None = None


def parse_sse(lines) -> Transcript:
    """Parse the `data: {...}` lines the runtime streams back."""
    out = Transcript()
    parts: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line.startswith("data:"):
            continue
        try:
            payload = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if "error" in payload:
            out.error = str(payload["error"])
        event = payload.get("event", {})
        delta = event.get("contentBlockDelta", {}).get("delta", {})
        if "text" in delta:
            parts.append(delta["text"])
        start = event.get("contentBlockStart", {}).get("start", {})
        if "toolUse" in start:
            out.tools.append(start["toolUse"].get("name", ""))
    out.text = "".join(parts)
    return out
