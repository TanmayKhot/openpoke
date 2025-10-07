from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any

from ..models import ChatHistoryClearResponse, ChatHistoryResponse, ChatRequest
from ..services import get_conversation_log, get_trigger_service, handle_chat_request, get_gmail_seen_store, get_timezone_store
from ..services.conversation.cache import get_conversation_cache
from ..services.conversation.summarization.working_memory_log import get_working_memory_log
from ..services.secret_mode import set_incognito_mode, get_incognito_mode_status, clear_session_memory

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/send", response_class=JSONResponse, summary="Submit a chat message and receive a completion")
# Handle incoming chat messages and route them to the interaction agent
async def chat_send(
    payload: ChatRequest,
) -> JSONResponse:
    return await handle_chat_request(payload)


@router.get("/history", response_model=ChatHistoryResponse)
# Retrieve the conversation history from the log
def chat_history() -> ChatHistoryResponse:
    log = get_conversation_log()
    return ChatHistoryResponse(messages=log.to_chat_messages())


@router.delete("/history", response_model=ChatHistoryClearResponse)
def clear_history() -> ChatHistoryClearResponse:
    from ..services import get_execution_agent_logs, get_agent_roster

    # Clear conversation log
    log = get_conversation_log()
    log.clear()

    # Clear execution agent logs
    execution_logs = get_execution_agent_logs()
    execution_logs.clear_all()

    # Clear agent roster
    roster = get_agent_roster()
    roster.clear()

    # Clear stored triggers
    trigger_service = get_trigger_service()
    trigger_service.clear_all()

    return ChatHistoryClearResponse()


@router.post("/memory/reset")
def reset_memory() -> Dict[str, Any]:
    """Reset all memory and cache completely."""
    from ..services import get_execution_agent_logs, get_agent_roster
    from ..openrouter_client.client import clear_response_cache

    # Clear conversation log
    log = get_conversation_log()
    log.clear()

    # Clear execution agent logs
    execution_logs = get_execution_agent_logs()
    execution_logs.clear_all()

    # Clear agent roster
    roster = get_agent_roster()
    roster.clear()

    # Clear stored triggers
    trigger_service = get_trigger_service()
    trigger_service.clear_all()

    # Clear conversation cache
    cache = get_conversation_cache()
    cache.clear()

    # Clear response cache
    clear_response_cache()

    # Clear working memory log
    working_memory = get_working_memory_log()
    working_memory.clear()

    # Clear Gmail seen store
    gmail_seen = get_gmail_seen_store()
    gmail_seen.clear()

    # Clear timezone store
    timezone_store = get_timezone_store()
    timezone_store.clear()

    # Clear session memory
    clear_session_memory()

    return {"message": "Memory reset successfully", "ok": True}


@router.post("/memory/pause")
def pause_memory() -> Dict[str, Any]:
    """Pause memory saving - conversations won't be saved to memory."""
    set_incognito_mode(True)
    return {"message": "Incognito mode enabled - conversations not saved", "ok": True}


@router.post("/memory/resume")
def resume_memory() -> Dict[str, Any]:
    """Resume memory saving - conversations will be saved to memory again."""
    set_incognito_mode(False)
    return {"message": "Incognito mode disabled - conversations saved", "ok": True}


@router.get("/memory/status")
def get_memory_status() -> Dict[str, Any]:
    """Get current memory status (paused/resumed)."""
    return get_incognito_mode_status()


__all__ = ["router"]
