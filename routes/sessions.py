"""
Router Gestione Sessioni e Storico Conversazioni
Supporta:
- Elenco sessioni salvate
- Caricamento cronologia messaggi per sessione
- Rinomina e cancellazione sessioni
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import verify_token
import database

router = APIRouter(prefix="/api/v1/sessions", tags=["Sessioni & Storico"])

class CreateSessionRequest(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None

class RenameSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)

class MessageInput(BaseModel):
    role: str
    content: str
    media_url: Optional[str] = None

class BatchMessagesInput(BaseModel):
    title: Optional[str] = None
    messages: List[MessageInput]

@router.get("", dependencies=[Depends(verify_token)])
async def get_sessions():
    """Elenca tutte le sessioni archiviate nel database SQLite ordinate per data."""
    return {"sessions": database.list_sessions()}

@router.post("", dependencies=[Depends(verify_token)])
async def create_new_session(payload: Optional[CreateSessionRequest] = None):
    """Crea una nuova sessione di chat."""
    title = payload.title if payload else None
    sid = payload.id if payload and payload.id else None
    session_id = database.create_session(session_id=sid, title=title)
    session = database.get_session(session_id)
    return {"session": session}

@router.post("/{session_id}/sync", dependencies=[Depends(verify_token)])
async def sync_session_messages(session_id: str, payload: BatchMessagesInput):
    """Sincronizza una sessione completa con tutti i suoi messaggi."""
    existing = database.get_session(session_id)
    if not existing:
        title = payload.title or "Conversazione Sincronizzata"
        database.create_session(session_id=session_id, title=title)
    for m in payload.messages:
        database.save_message(session_id, m.role, m.content, media_url=m.media_url)
    return {"status": "success", "session": database.get_session(session_id)}

@router.get("/{session_id}", dependencies=[Depends(verify_token)])
async def get_session_detail(session_id: str):
    """Restituisce le informazioni della sessione e la lista di tutti i messaggi associati."""
    session = database.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessione non trovata.")
    messages = database.get_session_messages(session_id)
    return {
        "session": session,
        "messages": messages
    }

@router.patch("/{session_id}", dependencies=[Depends(verify_token)])
async def rename_existing_session(session_id: str, payload: RenameSessionRequest):
    """Rinomina una sessione di chat."""
    success = database.rename_session(session_id, payload.title)
    if not success:
        raise HTTPException(status_code=404, detail="Sessione non trovata o titolo non valido.")
    return {"status": "success", "session": database.get_session(session_id)}

@router.delete("/{session_id}", dependencies=[Depends(verify_token)])
async def delete_existing_session(session_id: str):
    """Elimina una sessione e tutti i messaggi associati."""
    success = database.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Sessione non trovata.")
    return {"status": "success", "message": f"Sessione {session_id} eliminata."}

@router.post("/{session_id}/messages", dependencies=[Depends(verify_token)])
async def add_message_to_session(session_id: str, payload: MessageInput):
    """Salva manualmente un messaggio all'interno della sessione specificata."""
    msg_id = database.save_message(session_id, payload.role, payload.content, media_url=payload.media_url)
    return {"status": "success", "message_id": msg_id}
