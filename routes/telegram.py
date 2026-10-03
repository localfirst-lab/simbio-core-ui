import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import config
from auth import verify_token

router = APIRouter(prefix="/api/v1/telegram", tags=["Telegram Logger"])

BASE_DIR = Path(__file__).resolve().parent.parent
DIARIO_DIR = Path(os.getenv("DIARIO_DIR", str(Path.home() / "SimbioBot")))
STATIC_DIR = Path(os.getenv("STATIC_DIR", str(BASE_DIR / "static")))

def append_to_diario(evento: str, dettaglio: str, now_str: str) -> dict:
    """Archivia in formato strutturato JSON e TXT nel diario storico di Davide."""
    entry = {
        "timestamp": now_str,
        "evento": evento,
        "dettaglio": dettaglio
    }
    
    target_dirs = []
    if DIARIO_DIR.exists():
        target_dirs.append(DIARIO_DIR)
    if STATIC_DIR.exists():
        target_dirs.append(STATIC_DIR)
        
    for d in target_dirs:
        try:
            json_file = d / "diario_storico.json"
            txt_file = d / "diario_storico.txt"
            
            # 1. JSON
            data = []
            if json_file.exists():
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = []
            data.append(entry)
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            # 2. TXT
            txt_block = (
                f"=================================================================\n"
                f"DATA/ORA: {now_str}\n"
                f"EVENTO:   {evento}\n"
                f"DETTAGLIO:\n{dettaglio}\n"
                f"=================================================================\n\n"
            )
            with open(txt_file, "a", encoding="utf-8") as f:
                f.write(txt_block)
        except Exception as e:
            print(f"[DIARIO ERROR] Errore salvataggio in {d}: {e}")
            
    return entry

class TelegramLogPayload(BaseModel):
    evento: str = Field(..., description="Nome dell'evento (es. 'Avvio Modello', 'Connessione UI')")
    dettaglio: str = Field(..., description="Dettaglio o descrizione dell'operazione")
    categoria: str = Field(default="SISTEMA", description="Categoria dell'evento (SISTEMA, AGENTE, HARDWARE, NOTAIO)")

@router.post("/log", dependencies=[Depends(verify_token)])
async def post_telegram_log(payload: TelegramLogPayload):
    """Notarizza l'evento nel diario locale (JSON+TXT) e invia la card formattata al canale Telegram."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. Archiviazione persistente nei file diario (JSON e TXT)
    entry = append_to_diario(payload.evento, payload.dettaglio, now_str)

    # 2. Invio notifica sul canale Telegram
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return {
            "status": "SUCCESS_LOCAL_ONLY",
            "message": "Evento salvato nel diario JSON e TXT (Telegram non configurato).",
            "entry": entry
        }

    now_utc_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
    text = (
        f"📝 <b>REGISTRO NOTAIO STORICO</b>\n"
        f"🔷 <b>Evento:</b> {payload.evento}\n"
        f"🔶 <b>Dettaglio:</b> {payload.dettaglio}\n"
        f"🕒 <i>Timestamp:</i> {now_utc_str}\n"
        f"🏷️ <i>Origine:</i> {payload.categoria}"
    )

    tg_url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    tg_data = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(tg_url, json=tg_data)
            if resp.status_code != 200:
                print(f"[WARN Telegram API]: {resp.text}")
                return {
                    "status": "SAVED_LOCAL_API_WARN",
                    "message": f"Archiviato nel diario locale. Avviso Telegram: {resp.text}",
                    "entry": entry
                }
            return {
                "status": "SUCCESS",
                "message": "Evento notarizzato e inviato con successo al canale Telegram!",
                "entry": entry
            }
    except Exception as e:
        return {
            "status": "SAVED_LOCAL_ERROR_NETWORK",
            "message": f"Archiviato nel diario locale. Errore rete Telegram: {str(e)}",
            "entry": entry
        }
