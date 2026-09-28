"""Translate streamed write_file arguments into incremental file snapshots."""

import json
import time

from langchain_core.utils.json import parse_partial_json

if __package__:
    from .agent.tools import safe_path_for_project
    from .agent.workspace import project_root
else:
    from agent.tools import safe_path_for_project
    from agent.workspace import project_root


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class FileDrafts:
    def __init__(self):
        self.calls: dict[tuple, dict] = {}

    def consume(self, message, namespace=()):
        for chunk in getattr(message, "tool_call_chunks", []):
            key = (namespace, message.id, chunk.get("index", 0))
            call = self.calls.setdefault(key, {"name": "", "args": "", "sent": "", "time": 0.0})
            if chunk.get("name"):
                call["name"] = chunk["name"]
            call["args"] += chunk.get("args") or ""
            if call["name"] != "write_file" or time.monotonic() - call["time"] < 0.08:
                continue
            try:
                parsed = parse_partial_json(call["args"])
                if not isinstance(parsed, dict) or not isinstance(parsed.get("content"), str):
                    continue
                path = parsed.get("path")
                if not isinstance(path, str) or not path:
                    continue
                path = safe_path_for_project(path).relative_to(project_root()).as_posix()
            except (ValueError, TypeError):
                continue
            if parsed["content"] != call["sent"]:
                call.update(sent=parsed["content"], time=time.monotonic())
                yield {"type": "file_delta", "path": path, "content": parsed["content"]}
