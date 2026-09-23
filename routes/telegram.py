"""
Router Notifiche & Log Telegram
Invia registri storici ed eventi al canale Anima_Simbio.
"""
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import config
from auth import verify_token

router = APIRouter(prefix="/api/v1/telegram", tags=["Telegram Logger"])

class TelegramLogPayload(BaseModel):
    evento: str = Field(..., description="Nome dell'evento (es. 'Avvio Modello', 'Connessione UI')")
    dettaglio: str = Field(..., description="Dettaglio o descrizione dell'operazione")
    categoria: str = Field(default="SISTEMA", description="Categoria dell'evento (SISTEMA, AGENTE, HARDWARE)")

@router.post("/log", dependencies=[Depends(verify_token)])
async def post_telegram_log(payload: TelegramLogPayload):
    """Invia una card di registro storico formattata al canale Telegram."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return {
            "status": "SKIPPED",
            "message": "Credenziali Telegram non configurate nel file .env."
        }

    now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
    
    # Formattazione coerente con il canale Anima_Simbio
    text = (
        f"📝 <b>REGISTRO STORICO</b>\n"
        f"🔷 <b>Evento:</b> {payload.evento}\n"
        f"🔶 <b>Dettaglio:</b> {payload.dettaglio}\n"
        f"🕒 <i>Timestamp:</i> {now_str}\n"
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
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Errore API Telegram: {resp.text}"
                )
            return {"status": "SUCCESS", "message": "Log inviato con successo al canale Anima_Simbio."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante l'invio su Telegram: {str(e)}"
        )
