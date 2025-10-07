"""Global state management for incognito mode functionality."""

import threading
from typing import Optional, List, Dict, Any
from datetime import datetime

# Global state for incognito mode
_incognito_mode_enabled: bool = False
_incognito_mode_lock = threading.Lock()

# Session-only memory for incognito mode conversations
_session_memory: List[Dict[str, Any]] = []
_session_memory_lock = threading.Lock()


def is_incognito_mode_enabled() -> bool:
    """Check if incognito mode is currently enabled."""
    with _incognito_mode_lock:
        return _incognito_mode_enabled


def set_incognito_mode(enabled: bool) -> None:
    """Enable or disable incognito mode."""
    global _incognito_mode_enabled
    with _incognito_mode_lock:
        _incognito_mode_enabled = enabled
        # Clear session memory when disabling incognito mode
        if not enabled:
            clear_session_memory()


def get_incognito_mode_status() -> dict:
    """Get current incognito mode status."""
    return {
        "paused": is_incognito_mode_enabled(),
        "ok": True
    }


def add_to_session_memory(role: str, content: str, timestamp: Optional[str] = None) -> None:
    """Add a message to session-only memory."""
    if not is_incognito_mode_enabled():
        return
        
    with _session_memory_lock:
        _session_memory.append({
            "role": role,
            "content": content,
            "timestamp": timestamp or datetime.now().isoformat()
        })


def get_session_memory() -> List[Dict[str, Any]]:
    """Get all messages from session memory."""
    with _session_memory_lock:
        return _session_memory.copy()


def clear_session_memory() -> None:
    """Clear session memory."""
    with _session_memory_lock:
        _session_memory.clear()


def get_session_memory_for_context() -> List[Dict[str, str]]:
    """Get session memory formatted for LLM context."""
    with _session_memory_lock:
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in _session_memory
        ]
