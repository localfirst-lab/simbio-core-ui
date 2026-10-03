"""
Router Sicurezza VPS & Shield
Protezione attiva con Pydantic:
- Validazione rigorosa degli indirizzi IP e dei comandi di ban/unban
- Monitoraggio in tempo reale dei tentativi di intrusione SSH e API
- Esecuzione controllata dei comandi iptables per bloccare attaccanti
- Alert immediati su Telegram e sincronizzazione whitelist
"""

import json
import os
import re
import ipaddress
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

import config
from auth import verify_token

router = APIRouter(prefix="/api/v1/security", tags=["Sicurezza & Shield"])

BASE_DIR = Path(__file__).resolve().parent.parent
BANNED_FILE = Path("/var/log/vps_monitor/banned_ips.json")
if not BANNED_FILE.parent.exists():
    BANNED_FILE = BASE_DIR / "banned_ips.json"

# Whitelist fondamentale: non bloccare MAI localhost.
# Gli IP client fidati vanno configurati nella variabile SECURITY_WHITELIST_IPS nel file .env
ENV_WHITELIST = os.getenv("SECURITY_WHITELIST_IPS", "127.0.0.1,::1")
DEFAULT_WHITELIST = {ip.strip() for ip in ENV_WHITELIST.split(",") if ip.strip()}
DEFAULT_WHITELIST.add("127.0.0.1")
DEFAULT_WHITELIST.add("::1")

# -------------------------------------------------------------
# 1. MODELLI PYDANTIC PER VALIDAZIONE RIGOROSA
# -------------------------------------------------------------

class IPAddressValidator(BaseModel):
    ip: str = Field(..., description="Indirizzo IPv4 o IPv6 valido")

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        clean = v.strip()
        try:
            ipaddress.ip_address(clean)
        except ValueError:
            raise ValueError(f"'{v}' non è un indirizzo IP valido.")
        return clean


class BanIPRequest(BaseModel):
    ip: str = Field(..., description="Indirizzo IP da bloccare con iptables")
    reason: str = Field(default="Tentativi di accesso SSH non autorizzati", max_length=250)
    duration_hours: Optional[int] = Field(default=24, ge=1, le=8760, description="Durata del blocco in ore")

    @field_validator("ip")
    @classmethod
    def check_ip_and_whitelist(cls, v: str) -> str:
        clean = v.strip()
        try:
            ip_obj = ipaddress.ip_address(clean)
        except ValueError:
            raise ValueError(f"'{v}' non è un indirizzo IP valido.")
        
        if ip_obj.is_loopback or clean in DEFAULT_WHITELIST:
            raise ValueError(f"L'IP {clean} è presente nella WHITELIST o è localhost: IMPOSSIBILE BLOCCARE.")
        return clean


class UnbanIPRequest(BaseModel):
    ip: str = Field(..., description="Indirizzo IP da sbloccare")

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        clean = v.strip()
        try:
            ipaddress.ip_address(clean)
        except ValueError:
            raise ValueError(f"'{v}' non è un indirizzo IP valido.")
        return clean


class WhitelistIPRequest(BaseModel):
    ip: str = Field(..., description="Indirizzo IP da aggiungere alla whitelist")
    note: Optional[str] = Field(default="Accesso autorizzato", max_length=150)

    @field_validator("ip")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        clean = v.strip()
        try:
            ipaddress.ip_address(clean)
        except ValueError:
            raise ValueError(f"'{v}' non è un indirizzo IP valido.")
        return clean


class BannedIPInfo(BaseModel):
    ip: str
    reason: str
    banned_at: str
    banned_by: str = "security_agent"
    duration_hours: int = 24
    active: bool = True


# -------------------------------------------------------------
# 2. FUNZIONI DI GESTIONE FIREWALL E FILE STATO
# -------------------------------------------------------------

def load_banned_store() -> Dict[str, dict]:
    """Carica il registro degli IP bannati."""
    if BANNED_FILE.exists():
        try:
            with open(BANNED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_banned_store(store: Dict[str, dict]):
    """Salva il registro degli IP bannati."""
    try:
        BANNED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(BANNED_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[SECURITY] Errore salvataggio {BANNED_FILE}: {e}")


def execute_iptables_drop(ip: str) -> bool:
    """Inserisce la regola DROP in iptables se non già presente."""
    try:
        # Verifica se la regola esiste già
        check_cmd = ["iptables", "-C", "INPUT", "-s", ip, "-j", "DROP"]
        check = subprocess.run(check_cmd, capture_output=True, text=True)
        if check.returncode == 0:
            return True  # Regola già attiva

        # Inserisci come prima regola della catena INPUT
        insert_cmd = ["iptables", "-I", "INPUT", "-s", ip, "-j", "DROP"]
        res = subprocess.run(insert_cmd, capture_output=True, text=True)
        return res.returncode == 0
    except Exception as e:
        print(f"[SECURITY] Errore iptables drop su {ip}: {e}")
        return False


def execute_iptables_unban(ip: str) -> bool:
    """Rimuove la regola DROP in iptables."""
    try:
        del_cmd = ["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"]
        res = subprocess.run(del_cmd, capture_output=True, text=True)
        return res.returncode == 0
    except Exception as e:
        print(f"[SECURITY] Errore iptables unban su {ip}: {e}")
        return False


async def notify_telegram_security(title: str, message: str, level: str = "CRITICAL"):
    """Invia alert immediato sul bot/canale Telegram configurato."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return

    icon = "🚨" if level == "CRITICAL" else ("⚠️" if level == "WARN" else "🛡️")
    ts = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
    server_name = os.getenv("SERVER_NAME", os.getenv("HOST", "Linux VPS"))
    text = (
        f"{icon} <b>SICUREZZA VPS — {title}</b>\n\n"
        f"{message}\n\n"
        f"🕒 <i>Timestamp:</i> {ts}\n"
        f"🖥️ <i>Server:</i> <code>{server_name}</code>"
    )

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"[SECURITY] Errore invio alert Telegram: {e}")


# -------------------------------------------------------------
# 3. ENDPOINT DI CONTROLLO SICUREZZA
# -------------------------------------------------------------

@router.get("/status", dependencies=[Depends(verify_token)])
async def get_security_status(request: Request):
    """Restituisce lo stato globale del firewall, whitelist e IP bloccati."""
    client_ip = request.client.host if request.client else "N/A"
    
    # Leggi gli IP bannati salvati
    store = load_banned_store()
    
    # Controlla regole iptables attive
    iptables_drops = []
    try:
        res = subprocess.run(["iptables", "-L", "INPUT", "-n", "--line-numbers"], capture_output=True, text=True, timeout=3.0)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "DROP" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        iptables_drops.append(parts[4])
    except Exception:
        pass

    # Analisi veloce degli ultimi tentativi di accesso falliti da auth.log
    recent_fails = []
    auth_log_path = Path("/var/log/auth.log")
    if auth_log_path.exists():
        try:
            # Ultime 80 righe
            res = subprocess.run(["tail", "-n", "80", "/var/log/auth.log"], capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0:
                pattern = re.compile(r'Failed password for (?:invalid user )?(\w+) from (\d+\.\d+\.\d+\.\d+)')
                for line in res.stdout.splitlines():
                    m = pattern.search(line)
                    if m:
                        recent_fails.append({
                            "user": m.group(1),
                            "ip": m.group(2),
                            "raw": line[:120]
                        })
        except Exception:
            pass

    return {
        "status": "SHIELD_ACTIVE",
        "client_ip": client_ip,
        "is_client_whitelisted": client_ip in DEFAULT_WHITELIST,
        "firewall": {
            "type": "iptables",
            "active_drops_count": len(iptables_drops),
            "active_drops": iptables_drops
        },
        "banned_ips": store,
        "whitelist": sorted(list(DEFAULT_WHITELIST)),
        "recent_attacks_detected": recent_fails[-15:]
    }


@router.post("/ban", dependencies=[Depends(verify_token)])
async def ban_ip_endpoint(payload: BanIPRequest):
    """
    Blocca un IP attaccante con iptables e registra l'evento.
    Protetto da Pydantic: rifiuta IP non validi o presenti in Whitelist.
    """
    ip = payload.ip
    store = load_banned_store()

    # Esegui iptables DROP
    success = execute_iptables_drop(ip)
    now_str = datetime.now(timezone.utc).isoformat()

    store[ip] = {
        "ip": ip,
        "reason": payload.reason,
        "banned_at": now_str,
        "duration_hours": payload.duration_hours,
        "active": True
    }
    save_banned_store(store)

    # Notifica Telegram
    await notify_telegram_security(
        title="IP BLOCCATO CON SUCCESSO",
        message=(
            f"🚫 <b>IP:</b> <code>{ip}</code>\n"
            f"⚠️ <b>Motivo:</b> {payload.reason}\n"
            f"⏱️ <b>Durata:</b> {payload.duration_hours} ore\n"
            f"🛡️ <b>Azione:</b> Regola iptables DROP inserita"
        ),
        level="CRITICAL"
    )

    return {
        "status": "SUCCESS",
        "message": f"IP {ip} bloccato con successo.",
        "iptables_applied": success,
        "details": store[ip]
    }


@router.post("/unban", dependencies=[Depends(verify_token)])
async def unban_ip_endpoint(payload: UnbanIPRequest):
    """
    Rimuove il blocco iptables per un IP precedentemente bannato.
    """
    ip = payload.ip
    store = load_banned_store()

    success = execute_iptables_unban(ip)

    if ip in store:
        store[ip]["active"] = False
        store[ip]["unbanned_at"] = datetime.now(timezone.utc).isoformat()
        save_banned_store(store)

    await notify_telegram_security(
        title="IP SBLOCCATO",
        message=f"✅ <b>IP:</b> <code>{ip}</code> rimosso dal blocco iptables.",
        level="INFO"
    )

    return {
        "status": "SUCCESS",
        "message": f"IP {ip} sbloccato.",
        "iptables_removed": success
    }


@router.post("/whitelist", dependencies=[Depends(verify_token)])
async def add_to_whitelist(payload: WhitelistIPRequest):
    """Aggiunge un IP legittimo alla whitelist protetta."""
    ip = payload.ip
    DEFAULT_WHITELIST.add(ip)
    
    # Rimuovi eventuale ban per sicurezza
    execute_iptables_unban(ip)

    return {
        "status": "SUCCESS",
        "message": f"IP {ip} aggiunto alla whitelist con successo.",
        "whitelist": sorted(list(DEFAULT_WHITELIST))
    }
