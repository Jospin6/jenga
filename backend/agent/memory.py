"""Bounded conversation and current-project context shared by graph nodes."""

import json

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

from .tools import safe_read_file
from .workspace import project_root

RECENT_MESSAGE_LIMIT = 12
CONVERSATION_CHAR_LIMIT = 32_000
FILE_CONTEXT_CHAR_LIMIT = 24_000
COMPLETION_MESSAGE = "Votre site est prêt. Vous pouvez le prévisualiser ou demander des modifications."


def conversation_window(messages: list[AnyMessage]) -> list[AnyMessage]:
    """Keep the initial user request and the most recent exchanges."""
    recent = messages[-RECENT_MESSAGE_LIMIT:]
    initial = next((message for message in messages if message.type == "human"), None)
    if initial is not None and all(message.id != initial.id for message in recent):
        return [initial, *recent]
    return recent


def messages_from_history(history: list[dict], project_id: str) -> list[AnyMessage]:
    messages = []
    for index, item in enumerate(history):
        message_type = HumanMessage if item["role"] == "user" else AIMessage
        messages.append(message_type(content=item["content"], id=f"{project_id}:{index}"))
    return conversation_window(messages)


def conversation_context(messages: list[AnyMessage]) -> str:
    exchanges = [f"{message.type.upper()}: {message.content}" for message in conversation_window(messages)]
    text = "\n\n".join(exchanges)
    if len(text) <= CONVERSATION_CHAR_LIMIT:
        return text
    # Preserve both the original brief and the latest request in long chats.
    initial = exchanges[0][:12_000]
    marker = "\n\n[Older conversation omitted]\n\n"
    return initial + marker + text[-(CONVERSATION_CHAR_LIMIT - len(initial) - len(marker)):]


def project_context(previous_plan) -> str:
    """Read bounded snapshots; full files remain available through the tools."""
    parts = []
    if previous_plan:
        plan = previous_plan.model_dump() if hasattr(previous_plan, "model_dump") else previous_plan
        parts.append("PREVIOUS PROJECT PLAN:\n" + json.dumps(plan, ensure_ascii=False)[:10_000])
    root = project_root()
    paths = sorted(
        (path.relative_to(root).as_posix() for path in root.rglob("*")
         if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root)),
        key=lambda name: (name != "index.html", name),
    )
    if paths:
        parts.append("EXISTING PROJECT FILES:\n" + "\n".join(paths)[:8_000])
        remaining = FILE_CONTEXT_CHAR_LIMIT
        for path in paths:
            if remaining <= 0:
                break
            content = safe_read_file(path)
            if not content:
                continue
            excerpt = content[:min(8_000, remaining)]
            remaining -= len(excerpt)
            if len(excerpt) < len(content):
                excerpt += "\n[Excerpt only; use read_file for the complete file]"
            parts.append(f"CURRENT FILE {path}:\n{excerpt}")
    return "\n\n".join(parts)
