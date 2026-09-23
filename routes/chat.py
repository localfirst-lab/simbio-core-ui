"""
Router Chat & Modelli
Gestisce:
- OpenAI-compatible endpoint per Zed IDE (/v1/chat/completions, /v1/models)
- Simbio UI endpoint SSE (/api/v1/chat/stream) con eventi e battito neurale
"""
import time
import json
import uuid
import base64
from pathlib import Path
from typing import Any, AsyncGenerator, List, Optional
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent


import config
from auth import verify_token
import database

router = APIRouter(tags=["Chat & Modelli"])

# Modelli Pydantic per compatibilità OpenAI
class ChatMessage(BaseModel):
    role: str
    content: str

class OpenAIChatRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None

class SimbioChatRequest(BaseModel):
    session_id: Optional[str] = None
    prompt: Optional[str] = None
    messages: Optional[List[ChatMessage]] = None
    model: Optional[str] = None
    media_url: Optional[str] = None
    system_prompt: Optional[str] = "Sei Simbio, un'intelligenza artificiale neurale ed empatica."

# -------------------------------------------------------------
# 1. LISTA MODELLI (Ollama -> OpenAI Format & Simbio)
# -------------------------------------------------------------
@router.get("/v1/models", dependencies=[Depends(verify_token)])
@router.get("/api/v1/models", dependencies=[Depends(verify_token)])
async def list_models():
    """Restituisce la lista dei modelli installati su Ollama in formato compatibile OpenAI."""
    url = f"{config.OLLAMA_BASE_URL}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            
            models_list = []
            for item in data.get("models", []):
                name = item.get("name", "")
                models_list.append({
                    "id": name,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "simbio-vps",
                    "details": item.get("details", {})
                })
                
            return {"object": "list", "data": models_list}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Impossibile comunicare con Ollama: {str(e)}"
        )

# -------------------------------------------------------------
# 2. OPENAI COMPLIANT CHAT (Per Zed IDE e standard clients)
# -------------------------------------------------------------
@router.post("/v1/chat/completions", dependencies=[Depends(verify_token)])
async def openai_chat_completions(payload: OpenAIChatRequest):
    """Endpoint compatibile OpenAI standard, supporta streaming e risposta singola per Zed IDE."""
    selected_model = payload.model or config.DEFAULT_MODEL
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    ollama_messages = [{"role": m.role, "content": m.content} for m in payload.messages]
    ollama_payload = {
        "model": selected_model,
        "messages": ollama_messages,
        "stream": payload.stream,
        "options": {
            "temperature": payload.temperature,
            "num_thread": 6
        }
    }

    if payload.stream:
        async def stream_generator() -> AsyncGenerator[str, None]:
            url = f"{config.OLLAMA_BASE_URL}/api/chat"
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=ollama_payload) as response:
                    if response.status_code != 200:
                        yield f"data: {json.dumps({'error': 'Errore da Ollama'})}\n\n"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            delta_content = chunk.get("message", {}).get("content", "")
                            is_done = chunk.get("done", False)

                            sse_data = {
                                "id": chat_id,
                                "object": "chat.completion.chunk",
                                "created": created_ts,
                                "model": selected_model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": delta_content},
                                    "finish_reason": "stop" if is_done else None
                                }]
                            }
                            yield f"data: {json.dumps(sse_data)}\n\n"

                            if is_done:
                                yield "data: [DONE]\n\n"
                                break
                        except Exception:
                            continue

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    # Risposta sincrona / non-streaming
    url = f"{config.OLLAMA_BASE_URL}/api/chat"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=ollama_payload)
            resp.raise_for_status()
            data = resp.json()

            full_text = data.get("message", {}).get("content", "")
            return {
                "id": chat_id,
                "object": "chat.completion",
                "created": created_ts,
                "model": selected_model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": full_text
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                }
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Errore generazione Ollama: {str(e)}"
        )

# -------------------------------------------------------------
# 3. SIMBIO STREAM (Ottimizzato per Simbio Mobile UI)
# -------------------------------------------------------------
@router.post("/api/v1/chat/stream", dependencies=[Depends(verify_token)])
async def simbio_chat_stream(payload: SimbioChatRequest):
    """
    Endpoint SSE specifico per Simbio Mobile UI.
    Supporta animazione cardiaca (pulse) e stream istantaneo dei frammenti di testo.
    """
    selected_model = payload.model or config.DEFAULT_MODEL
    
    # Costruzione cronologia messaggi con continuità di memoria contestuale
    messages = []
    if payload.system_prompt:
        messages.append({"role": "system", "content": payload.system_prompt})
    
    user_prompt_text = payload.prompt or ""

    if payload.messages:
        for m in payload.messages:
            messages.append({"role": m.role, "content": m.content})
        if payload.messages[-1].role == "user":
            user_prompt_text = payload.messages[-1].content
    else:
        # Recupera lo storico dei turni precedenti dal database SQLite della sessione
        if payload.session_id:
            try:
                past_messages = database.get_session_messages(payload.session_id)
                # Mantieni gli ultimi 12 messaggi per garantire memoria perfetta e fluidità su CPU
                recent_history = past_messages[-12:] if len(past_messages) > 12 else past_messages
                for h in recent_history:
                    content_str = h["content"]
                    if h.get("media_url") and h["role"] == "user":
                        content_str = f"[Foto/Screenshot allegato in precedenza]\n{content_str}"
                    messages.append({"role": h["role"], "content": content_str})
            except Exception as e:
                print(f"[DB ERROR] Errore recupero cronologia sessione: {e}")

        if not user_prompt_text and payload.media_url:
            user_prompt_text = "Analizza questa immagine."

        if not user_prompt_text and not payload.media_url:
            raise HTTPException(status_code=400, detail="Specificare un 'prompt' o una lista di 'messages'.")

        messages.append({"role": "user", "content": user_prompt_text})

    # Supporto multimodale: codifica base64 con ottimizzazione per inferenza rapida su CPU
    if payload.media_url:
        img_rel = payload.media_url.lstrip("/")
        img_path = BASE_DIR / img_rel
        if img_path.exists():
            try:
                from PIL import Image
                import io
                with Image.open(img_path) as im:
                    im = im.convert("RGB")
                    im.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    buffer = io.BytesIO()
                    im.save(buffer, format="JPEG", quality=85)
                    b64_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    if messages and messages[-1].get("role") == "user":
                        messages[-1]["images"] = [b64_str]
            except Exception:
                try:
                    b64_str = base64.b64encode(img_path.read_bytes()).decode("utf-8")
                    if messages and messages[-1].get("role") == "user":
                        messages[-1]["images"] = [b64_str]
                except Exception as e2:
                    print(f"[MEDIA ERROR] Errore codifica immagine base64: {e2}")

    # Salva il nuovo messaggio utente nel database
    if payload.session_id and (user_prompt_text or payload.media_url):
        try:
            database.save_message(payload.session_id, "user", user_prompt_text, media_url=payload.media_url)
        except Exception as e:
            print(f"[DB ERROR] Impossibile salvare messaggio utente: {e}")

    ollama_payload = {
        "model": selected_model,
        "messages": messages,
        "stream": True,
        "options": {
            "num_thread": 6,
            "num_ctx": 4096
        }
    }

    async def sse_simbio_generator() -> AsyncGenerator[str, None]:
        # Evento iniziale: nucleo attivo, inizia a elaborare (avvia l'impulso)
        yield f"event: pulse\ndata: {json.dumps({'status': 'thinking', 'pulse': True})}\n\n"
        
        url = f"{config.OLLAMA_BASE_URL}/api/chat"
        accumulated_assistant_text = ""

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", url, json=ollama_payload) as response:
                    if response.status_code != 200:
                        yield f"event: error\ndata: {json.dumps({'error': 'Errore connessione con nucleo Ollama'})}\n\n"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            delta_token = chunk.get("message", {}).get("content", "")
                            is_done = chunk.get("done", False)

                            if delta_token:
                                accumulated_assistant_text += delta_token
                                yield f"event: token\ndata: {json.dumps({'token': delta_token})}\n\n"

                            if is_done:
                                # Salva la risposta completa dell'assistente nel database
                                if payload.session_id and accumulated_assistant_text.strip():
                                    try:
                                        database.save_message(payload.session_id, "assistant", accumulated_assistant_text.strip())
                                    except Exception as dbe:
                                        print(f"[DB ERROR] Impossibile salvare risposta assistente: {dbe}")

                                stats = {
                                    "status": "idle",
                                    "pulse": False,
                                    "session_id": payload.session_id,
                                    "eval_duration_ms": int(chunk.get("eval_duration", 0) / 1e6),
                                    "tokens_evaluated": chunk.get("eval_count", 0)
                                }
                                yield f"event: done\ndata: {json.dumps(stats)}\n\n"
                                break
                        except Exception:
                            continue
        except Exception as err:
            yield f"event: error\ndata: {json.dumps({'error': str(err)})}\n\n"

    return StreamingResponse(
        sse_simbio_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
