from __future__ import annotations

import re
import threading
from datetime import datetime
from html import escape, unescape
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Protocol, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..config import get_settings
from ..logging_config import logger
from ..models import ChatMessage
from .timezone_store import get_timezone_store


class TranscriptFormatter(Protocol):
    def __call__(self, tag: str, timestamp: str, payload: str) -> str:  # pragma: no cover - typing protocol
        ...


def _encode_payload(payload: str) -> str:
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = normalized.replace("\n", "\\n")
    return escape(collapsed, quote=False)


def _decode_payload(payload: str) -> str:
    return unescape(payload).replace("\\n", "\n")


def _current_timestamp() -> str:
    store = get_timezone_store()
    tz_name = store.get_timezone()
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("unknown timezone; defaulting to UTC", extra={"timezone": tz_name})
        tz = ZoneInfo("UTC")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "timezone resolution failed; defaulting to UTC", extra={"error": str(exc)}
        )
        tz = ZoneInfo("UTC")
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


def _default_formatter(tag: str, timestamp: str, payload: str) -> str:
    encoded = _encode_payload(payload)
    return f"<{tag} timestamp=\"{timestamp}\">{encoded}</{tag}>\n"


_ATTR_PATTERN = re.compile(r"(\w+)\s*=\s*\"([^\"]*)\"")


class ConversationLog:
    """Append-only conversation log persisted to disk for the interaction agent."""

    def __init__(self, path: Path, formatter: TranscriptFormatter = _default_formatter):
        self._path = path
        self._formatter = formatter
        self._lock = threading.Lock()
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("conversation log directory creation failed", extra={"error": str(exc)})

    def _append(self, tag: str, payload: str) -> None:
        timestamp = _current_timestamp()
        entry = self._formatter(tag, timestamp, str(payload))
        with self._lock:
            try:
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(entry)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "conversation log append failed",
                    extra={"error": str(exc), "tag": tag, "path": str(self._path)},
                )
                raise

    def _parse_line(self, line: str) -> Optional[Tuple[str, str, str]]:
        stripped = line.strip()
        if not stripped.startswith("<") or "</" not in stripped:
            return None
        open_end = stripped.find(">")
        if open_end == -1:
            return None
        open_tag_content = stripped[1:open_end]
        if " " in open_tag_content:
            tag, attr_string = open_tag_content.split(" ", 1)
        else:
            tag, attr_string = open_tag_content, ""
        close_start = stripped.rfind("</")
        close_end = stripped.rfind(">")
        if close_start == -1 or close_end == -1:
            return None
        closing_tag = stripped[close_start + 2 : close_end]
        if closing_tag != tag:
            return None
        payload = stripped[open_end + 1 : close_start]
        attributes: Dict[str, str] = {
            match.group(1): match.group(2) for match in _ATTR_PATTERN.finditer(attr_string)
        }
        timestamp = attributes.get("timestamp", "")
        return tag, timestamp, _decode_payload(payload)

    def iter_entries(self) -> Iterator[Tuple[str, str, str]]:
        with self._lock:
            try:
                lines = self._path.read_text(encoding="utf-8").splitlines()
            except FileNotFoundError:
                lines = []
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "conversation log read failed", extra={"error": str(exc), "path": str(self._path)}
                )
                raise
        for line in lines:
            item = self._parse_line(line)
            if item is not None:
                yield item

    def load_transcript(self) -> str:
        parts: List[str] = []
        for tag, timestamp, payload in self.iter_entries():
            safe_payload = escape(payload, quote=False)
            if timestamp:
                parts.append(f"<{tag} timestamp=\"{timestamp}\">{safe_payload}</{tag}>")
            else:
                parts.append(f"<{tag}>{safe_payload}</{tag}>")
        return "\n".join(parts)

    def record_user_message(self, content: str) -> None:
        self._append("user_message", content)

    def record_agent_message(self, content: str) -> None:
        self._append("agent_message", content)

    def record_reply(self, content: str) -> None:
        self._append("poke_reply", content)

    def to_chat_messages(self) -> List[ChatMessage]:
        messages: List[ChatMessage] = []
        for tag, timestamp, payload in self.iter_entries():
            normalized_timestamp = timestamp or None
            if tag == "user_message":
                messages.append(
                    ChatMessage(role="user", content=payload, timestamp=normalized_timestamp)
                )
            elif tag == "poke_reply":
                messages.append(
                    ChatMessage(
                        role="assistant", content=payload, timestamp=normalized_timestamp
                    )
                )
        return messages

    def clear(self) -> None:
        with self._lock:
            try:
                if self._path.exists():
                    self._path.unlink()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "conversation log clear failed", extra={"error": str(exc), "path": str(self._path)}
                )
            finally:
                self._ensure_directory()


_conversation_log = ConversationLog(get_settings().resolved_conversation_log_path)


def get_conversation_log() -> ConversationLog:
    return _conversation_log


__all__ = ["ConversationLog", "get_conversation_log"]
