"""
Router Telemetria & Stato Hardware VPS
Fornisce metriche in tempo reale per la schermata "Stato Hardware" della UI Simbio:
- RAM utilizzata / totale / percentuale
- Carico CPU & Temperatura
- Uptime di sistema
- Modelli AI attualmente caricati in VRAM/RAM (Ollama ps)
"""
import os
import time
import shutil
import psutil
import httpx
import subprocess
import re
from fastapi import APIRouter, Depends
import config
from auth import verify_token

router = APIRouter(prefix="/api/v1/system", tags=["Sistema & Telemetria"])

def get_temperature() -> str:
    """Tenta di leggere la temperatura della CPU o GPU su Linux."""
    try:
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        return f"{entries[0].current:.1f} °C"
    except Exception:
        pass
    return "Normale"

def format_uptime(seconds: float) -> str:
    """Formatta i secondi in formato leggibile hh:mm:ss."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d > 0:
        return f"{d}g {h}h {m}m"
    return f"{h}h {m}m {s}s"

@router.get("/status", dependencies=[Depends(verify_token)])
async def get_system_status():
    """Restituisce le metriche hardware complete della VPS."""
    # RAM
    ram = psutil.virtual_memory()
    ram_used_gb = round(ram.used / (1024 ** 3), 2)
    ram_total_gb = round(ram.total / (1024 ** 3), 2)
    
    # CPU
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count(logical=True)
    
    # DISCO
    disk = shutil.disk_usage("/")
    disk_free_gb = round(disk.free / (1024 ** 3), 1)
    disk_total_gb = round(disk.total / (1024 ** 3), 1)
    disk_percent = round((disk.used / disk.total) * 100, 1)

    # UPTIME
    uptime_seconds = time.time() - psutil.boot_time()
    uptime_str = format_uptime(uptime_seconds)

    # MODELLI ATTIVI IN OLLAMA (RAM/VRAM)
    active_models = []
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{config.OLLAMA_BASE_URL}/api/ps")
            if resp.status_code == 200:
                ps_data = resp.json()
                for m in ps_data.get("models", []):
                    active_models.append({
                        "name": m.get("name"),
                        "size_vram_gb": round(m.get("size_vram", 0) / (1024 ** 3), 2),
                        "expires_at": m.get("expires_at")
                    })
    except Exception:
        pass

    return {
        "status": "ONLINE",
        "timestamp": int(time.time()),
        "uptime": uptime_str,
        "telemetry": {
            "ram": {
                "used_gb": ram_used_gb,
                "total_gb": ram_total_gb,
                "percent": ram.percent,
                "display": f"{ram_used_gb} GB / {ram_total_gb} GB ({ram.percent}%)"
            },
            "cpu": {
                "percent": cpu_percent,
                "cores": cpu_count,
                "display": f"{cpu_percent}% ({cpu_count} Core)"
            },
            "temperatura": {
                "valore": get_temperature(),
                "stato": "OK"
            },
            "disco": {
                "usato_percent": disk_percent,
                "libero_gb": disk_free_gb,
                "totale_gb": disk_total_gb,
                "display": f"{disk_free_gb} GB liberi su {disk_total_gb} GB"
            },
            "nucleo": {
                "ollama_online": True,
                "modelli_attivi": active_models,
                "default_model": config.DEFAULT_MODEL
            }
        }
    }

@router.get("/logs", dependencies=[Depends(verify_token)])
async def get_system_logs(
    service: str = "all", 
    lines: int = 60, 
    level: str = "all"
):
    """
    Restituisce gli ultimi log reali della VPS per la Console Terminale:
    - service: "all", "api" (simbio-api), "ollama", "system"
    - lines: 10..200 (default 60)
    - level: "all", "errors", "warnings"
    """
    lines = min(max(lines, 10), 200)
    cmd = []
    
    if service == "api":
        cmd = ["journalctl", "-u", "simbio-api", "-n", str(lines), "--no-pager", "-o", "short-iso"]
    elif service == "ollama":
        cmd = ["journalctl", "-u", "ollama", "-n", str(lines), "--no-pager", "-o", "short-iso"]
    elif service == "system":
        cmd = ["journalctl", "-p", "3", "-n", str(lines), "--no-pager", "-o", "short-iso"]
    else:  # all
        cmd = ["journalctl", "-u", "simbio-api", "-u", "ollama", "-n", str(lines), "--no-pager", "-o", "short-iso"]

    raw_output = []
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4.0)
        if proc.stdout:
            raw_output = proc.stdout.splitlines()
    except Exception as e:
        raw_output = [f"Errore lettura log journalctl: {str(e)}"]

    error_patterns = [r"\berror\b", r"\bexception\b", r"\btraceback\b", r"\bfailed\b", r"\bcritical\b", r"\b50[0-9]\b", r"\b40[134]\b"]
    warn_patterns = [r"\bwarn\b", r"\bwarning\b"]

    parsed = []
    for line in raw_output:
        line_clean = line.strip()
        if not line_clean:
            continue

        lower = line_clean.lower()
        is_error = any(re.search(p, lower) for p in error_patterns)
        is_warn = any(re.search(p, lower) for p in warn_patterns)

        log_lvl = "ERROR" if is_error else ("WARN" if is_warn else "INFO")

        if level == "errors" and log_lvl != "ERROR":
            continue
        if level == "warnings" and log_lvl not in ("ERROR", "WARN"):
            continue

        # Identifica sorgente
        src = "SYS"
        if "simbio-api" in line_clean or "uvicorn" in line_clean:
            src = "API"
        elif "ollama" in line_clean:
            src = "OLLAMA"
        elif "nginx" in line_clean:
            src = "NGINX"

        # Estrai timestamp breve se presente
        ts = ""
        msg = line_clean
        parts = line_clean.split(" ", 2)
        if len(parts) >= 3 and "T" in parts[0]:
            try:
                ts = parts[0].split("T")[1][:8]
                msg = parts[2]
            except Exception:
                pass

        parsed.append({
            "ts": ts,
            "src": src,
            "lvl": log_lvl,
            "msg": msg,
            "raw": line_clean
        })

    return {
        "status": "success",
        "service": service,
        "count": len(parsed),
        "logs": parsed
    }

