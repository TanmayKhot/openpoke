"""Interaction agent helpers for prompt construction."""

from html import escape
from pathlib import Path
from typing import Dict, List

from ...services.execution import get_agent_roster
from ...services.conversation.context_optimizer import get_context_optimizer
from ...models import ChatMessage

_prompt_path = Path(__file__).parent / "system_prompt.md"
SYSTEM_PROMPT = _prompt_path.read_text(encoding="utf-8").strip()


# Load and return the pre-defined system prompt from markdown file
def build_system_prompt() -> str:
    """Return the static system prompt for the interaction agent."""
    return SYSTEM_PROMPT


# Build structured message with conversation history, active agents, and current turn
def prepare_message_with_history(
    latest_text: str,
    transcript: str,
    message_type: str = "user",
) -> List[Dict[str, str]]:
    """Compose a message that bundles history, roster, and the latest turn."""
    sections: List[str] = []

    sections.append(_render_conversation_history(transcript))
    sections.append(f"<active_agents>\n{_render_active_agents()}\n</active_agents>")
    sections.append(_render_current_turn(latest_text, message_type))

    content = "\n\n".join(sections)
    return [{"role": "user", "content": content}]


# Build structured message with optimized context selection
def prepare_message_with_smart_context(
    latest_text: str,
    messages: List[ChatMessage],
    message_type: str = "user",
) -> List[Dict[str, str]]:
    """
    Compose a message with smart context optimization.
    
    Args:
        latest_text: Current user message or agent response
        messages: Full conversation messages
        message_type: Type of message ("user" or "agent")
        
    Returns:
        List of messages in OpenRouter format
    """
    # Get context optimizer
    optimizer = get_context_optimizer()
    
    # Optimize context
    optimization_result = optimizer.optimize_context(
        messages=messages,
        current_query=latest_text,
        agent_type="interaction"
    )
    
    # Build optimized transcript from selected segments
    optimized_transcript = _build_optimized_transcript(optimization_result)
    
    # Log optimization metrics
    _log_context_optimization(optimization_result, latest_text)
    
    # Build message sections
    sections: List[str] = []
    sections.append(_render_conversation_history(optimized_transcript))
    sections.append(f"<active_agents>\n{_render_active_agents()}\n</active_agents>")
    sections.append(_render_current_turn(latest_text, message_type))

    content = "\n\n".join(sections)
    return [{"role": "user", "content": content}]


# Format conversation transcript into XML tags for LLM context
def _render_conversation_history(transcript: str) -> str:
    history = transcript.strip()
    if not history:
        history = "None"
    return f"<conversation_history>\n{history}\n</conversation_history>"


# Format currently active execution agents into XML tags for LLM awareness
def _render_active_agents() -> str:
    roster = get_agent_roster()
    roster.load()
    agents = roster.get_agents()

    if not agents:
        return "None"

    rendered: List[str] = []
    for agent_name in agents:
        name = escape(agent_name or "agent", quote=True)
        rendered.append(f'<agent name="{name}" />')

    return "\n".join(rendered)


# Wrap the current message in appropriate XML tags based on sender type
def _render_current_turn(latest_text: str, message_type: str) -> str:
    tag = "new_agent_message" if message_type == "agent" else "new_user_message"
    body = latest_text.strip()
    return f"<{tag}>\n{body}\n</{tag}>"


# Build optimized transcript from context optimization result
def _build_optimized_transcript(optimization_result) -> str:
    """Build transcript from optimized context segments."""
    if not optimization_result.selected_segments:
        return "None"
    
    transcript_parts = []
    for segment in optimization_result.selected_segments:
        if segment.messages:
            # Convert messages to transcript format
            segment_transcript = _messages_to_transcript(segment.messages)
            transcript_parts.append(segment_transcript)
    
    return "\n\n".join(transcript_parts)


# Convert ChatMessage list to transcript format
def _messages_to_transcript(messages: List[ChatMessage]) -> str:
    """Convert ChatMessage list to transcript format."""
    transcript_parts = []
    for message in messages:
        if message.role == "user":
            transcript_parts.append(f"<user_message timestamp=\"{message.timestamp}\">{message.content}</user_message>")
        elif message.role == "assistant":
            transcript_parts.append(f"<assistant_message timestamp=\"{message.timestamp}\">{message.content}</assistant_message>")
        elif message.role == "agent":
            transcript_parts.append(f"<agent_message timestamp=\"{message.timestamp}\">{message.content}</agent_message>")
    
    return "\n".join(transcript_parts)


# Log context optimization metrics
def _log_context_optimization(optimization_result, current_query: str) -> None:
    """Log context optimization metrics for monitoring."""
    from ...logging_config import logger
    
    logger.info(
        "context optimization applied",
        extra={
            "strategy": optimization_result.optimization_strategy,
            "original_messages": optimization_result.original_message_count,
            "optimized_messages": optimization_result.optimized_message_count,
            "compression_ratio": optimization_result.compression_ratio,
            "estimated_tokens": optimization_result.total_tokens_estimate,
            "segments_count": len(optimization_result.selected_segments),
            "query_length": len(current_query),
        }
    )
