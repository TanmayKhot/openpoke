from __future__ import annotations

import re
import threading
from html import escape, unescape
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Protocol, Tuple

from ...config import get_settings
from ...logging_config import logger
from ...models import ChatMessage
from ...utils.timezones import now_in_user_timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - used for type checkers only
    from .summarization import WorkingMemoryLog
    from .cache import ConversationCache


_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_CONVERSATION_LOG_PATH = _DATA_DIR / "conversation" / "poke_conversation.log"


class TranscriptFormatter(Protocol):
    def __call__(self, tag: str, timestamp: str, payload: str) -> str:  # pragma: no cover - typing protocol
        ...


def _encode_payload(payload: str) -> str:
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = normalized.replace("\n", "\\n")
    return escape(collapsed, quote=False)


def _decode_payload(payload: str) -> str:
    return unescape(payload).replace("\\n", "\n")


def _default_formatter(tag: str, timestamp: str, payload: str) -> str:
    encoded = _encode_payload(payload)
    return f"<{tag} timestamp=\"{timestamp}\">{encoded}</{tag}>\n"


def _resolve_working_memory_log() -> "WorkingMemoryLog":
    from .summarization import get_working_memory_log

    return get_working_memory_log()


_ATTR_PATTERN = re.compile(r"(\w+)\s*=\s*\"([^\"]*)\"")


class ConversationLog:
    """Append-only conversation log persisted to disk for the interaction agent."""

    def __init__(self, path: Path, formatter: TranscriptFormatter = _default_formatter):
        self._path = path
        self._formatter = formatter
        self._lock = threading.Lock()
        self._ensure_directory()
        self._working_memory_log = _resolve_working_memory_log()
        self._cache = None  # Lazy initialization

    def _ensure_directory(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("conversation log directory creation failed", extra={"error": str(exc)})

    def _get_cache(self) -> "ConversationCache":
        """Get conversation cache instance (lazy initialization)."""
        if self._cache is None:
            from .cache import get_conversation_cache
            self._cache = get_conversation_cache()
        return self._cache

    def _invalidate_cache(self) -> None:
        """Invalidate conversation cache when new messages are added."""
        try:
            cache = self._get_cache()
            cache.invalidate_conversation("default")
            logger.debug("conversation cache invalidated after new message")
        except Exception as exc:
            logger.debug("failed to invalidate cache", extra={"error": str(exc)})

    def _append(self, tag: str, payload: str) -> str:
        timestamp = now_in_user_timezone("%Y-%m-%d %H:%M:%S")
        
        # Check if incognito mode is enabled - if so, don't write to disk
        try:
            from ..secret_mode import is_incognito_mode_enabled
            if is_incognito_mode_enabled():
                logger.info("Incognito mode enabled - skipping disk write for conversation log")
                return timestamp
        except ImportError:
            # Fallback if secret mode module is not available
            pass
        
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
        self._notify_summarization()
        return timestamp

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
        # Check if incognito mode is enabled
        try:
            from ..secret_mode import is_incognito_mode_enabled, add_to_session_memory
            if is_incognito_mode_enabled():
                # Add to session memory instead of persistent memory
                add_to_session_memory("user", content)
                logger.info("Incognito mode enabled - user message saved to session memory only")
                return
        except ImportError:
            # Fallback if secret mode module is not available
            pass
            
        timestamp = self._append("user_message", content)
        # Only update working memory if not in incognito mode
        try:
            from ..secret_mode import is_incognito_mode_enabled
            if not is_incognito_mode_enabled():
                self._working_memory_log.append_entry("user_message", content, timestamp)
        except ImportError:
            # Fallback if secret mode module is not available
            self._working_memory_log.append_entry("user_message", content, timestamp)
        # Only invalidate cache if not in incognito mode (since we're not saving to persistent storage)
        try:
            from ..secret_mode import is_incognito_mode_enabled
            if not is_incognito_mode_enabled():
                self._invalidate_cache()
        except ImportError:
            # Fallback if secret mode module is not available
            self._invalidate_cache()

    def record_agent_message(self, content: str) -> None:
        # Check if incognito mode is enabled
        try:
            from ..secret_mode import is_incognito_mode_enabled, add_to_session_memory
            if is_incognito_mode_enabled():
                # Add to session memory instead of persistent memory
                add_to_session_memory("assistant", content)
                logger.info("Incognito mode enabled - agent message saved to session memory only")
                return
        except ImportError:
            # Fallback if secret mode module is not available
            pass
            
        timestamp = self._append("agent_message", content)
        # Only update working memory if not in incognito mode
        try:
            from ..secret_mode import is_incognito_mode_enabled
            if not is_incognito_mode_enabled():
                self._working_memory_log.append_entry("agent_message", content, timestamp)
        except ImportError:
            # Fallback if secret mode module is not available
            self._working_memory_log.append_entry("agent_message", content, timestamp)
        # Only invalidate cache if not in incognito mode (since we're not saving to persistent storage)
        try:
            from ..secret_mode import is_incognito_mode_enabled
            if not is_incognito_mode_enabled():
                self._invalidate_cache()
        except ImportError:
            # Fallback if secret mode module is not available
            self._invalidate_cache()

    def record_reply(self, content: str) -> None:
        # Check if incognito mode is enabled
        try:
            from ..secret_mode import is_incognito_mode_enabled, add_to_session_memory
            if is_incognito_mode_enabled():
                # Add to session memory instead of persistent memory
                add_to_session_memory("assistant", content)
                logger.info("Incognito mode enabled - reply saved to session memory only")
                return
        except ImportError:
            # Fallback if secret mode module is not available
            pass
            
        timestamp = self._append("poke_reply", content)
        # Only update working memory if not in incognito mode
        try:
            from ..secret_mode import is_incognito_mode_enabled
            if not is_incognito_mode_enabled():
                self._working_memory_log.append_entry("poke_reply", content, timestamp)
        except ImportError:
            # Fallback if secret mode module is not available
            self._working_memory_log.append_entry("poke_reply", content, timestamp)
        # Only invalidate cache if not in incognito mode (since we're not saving to persistent storage)
        try:
            from ..secret_mode import is_incognito_mode_enabled
            if not is_incognito_mode_enabled():
                self._invalidate_cache()
        except ImportError:
            # Fallback if secret mode module is not available
            self._invalidate_cache()

    def record_wait(self, reason: str) -> None:
        """Record a wait marker that should not reach the user-facing chat history."""
        timestamp = self._append("wait", reason)
        # Only update working memory if not in incognito mode
        try:
            from ..secret_mode import is_incognito_mode_enabled
            if not is_incognito_mode_enabled():
                self._working_memory_log.append_entry("wait", reason, timestamp)
        except ImportError:
            # Fallback if secret mode module is not available
            self._working_memory_log.append_entry("wait", reason, timestamp)

    def _notify_summarization(self) -> None:
        # Don't trigger summarization in incognito mode
        try:
            from ..secret_mode import is_incognito_mode_enabled
            if is_incognito_mode_enabled():
                logger.info("Incognito mode enabled - skipping summarization")
                return
        except ImportError:
            # Fallback if secret mode module is not available
            pass
        
        settings = get_settings()
        if not settings.summarization_enabled:
            return

        try:
            from .summarization import schedule_summarization  # type: ignore import-not-found
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(
                "summarization scheduler unavailable",
                extra={"error": str(exc)},
            )
            return

        try:
            schedule_summarization()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "failed to schedule summarization",
                extra={"error": str(exc)},
            )

    def to_chat_messages(self) -> List[ChatMessage]:
        """Get chat messages, using cache when available."""
        # Check if incognito mode is enabled
        try:
            from ..secret_mode import is_incognito_mode_enabled, get_session_memory
            if is_incognito_mode_enabled():
                # In incognito mode, combine persistent memory with session memory
                persistent_messages = self._get_persistent_messages()
                session_messages = get_session_memory()
                
                # Convert session messages to ChatMessage format
                session_chat_messages = [
                    ChatMessage(
                        role=msg["role"], 
                        content=msg["content"], 
                        timestamp=msg.get("timestamp")
                    )
                    for msg in session_messages
                ]
                
                # Return persistent + session messages
                return persistent_messages + session_chat_messages
        except ImportError:
            # Fallback if secret mode module is not available
            pass

        # Normal mode: try cache first, then disk
        return self._get_persistent_messages()

    def _get_persistent_messages(self) -> List[ChatMessage]:
        """Get messages from persistent storage (cache or disk)."""
        # Try to get from cache first
        try:
            cache = self._get_cache()
            cached_messages = cache.get_conversation("default")
            if cached_messages:
                logger.debug("using cached conversation messages", extra={"count": len(cached_messages)})
                return cached_messages
        except Exception as exc:
            logger.debug("cache unavailable, falling back to disk", extra={"error": str(exc)})
        
        # Fallback to disk loading
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
            elif tag == "wait":
                # Wait markers are orchestration metadata and must not surface to the user
                continue
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
        try:
            self._working_memory_log.clear()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(
                "working memory clear skipped",
                extra={"error": str(exc)},
            )


_conversation_log = ConversationLog(_CONVERSATION_LOG_PATH)


def get_conversation_log() -> ConversationLog:
    return _conversation_log


__all__ = ["ConversationLog", "get_conversation_log"]
