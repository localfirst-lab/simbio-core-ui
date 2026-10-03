#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
  VPS_MONITOR_AGENT.PY (Simbio Security Shield v2.2)
  Agente di Sicurezza & Firewall Attivo per VPS Contabo
  Davide Carrieri — Simbio Ecosystem

  Funzionalità:
    1. Analisi auth.log in tempo reale:
       - Rileva tentativi di login SSH falliti (password/chiave)
       - Rileva tentativi con utenti inesistenti (admin, ubuntu, root...)
       - Rileva accessi riusciti da IP sconosciuti
    2. BLOCCO ATTIVO AUTOMATICO (Firewall Shield):
       - Applica regola iptables DROP istantanea per IP attaccanti
       - Whitelist protetta (IP personali di Davide sempre immuni)
       - Dynamic Whitelisting (auto-whitelist per accessi riusciti di Davide)
    3. Notifiche Intelligenti Anti-Spam (Digest Mode):
       - Alert CRITICO IMMEDIATO se qualcuno prova ad accedere come 'davide'
       - Report consolidato per i normali bot automatici (ogni 30 min o 5 bot)
    4. Persistenza e Sincronizzazione:
       - Salva registro /var/log/vps_monitor/banned_ips.json
       - Condiviso con Simbio API e Web UI Mobile
=================================================================
"""

import json
import os
import re
import subprocess
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ─── Configurazione ──────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "config_monitor.json"

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {
        "whitelist_ips": ["127.0.0.1", "::1", "<YOUR_CLIENT_IP_HERE>"],
        "expected_open_ports": [22, 53, 80, 443, 8000, 8550, 11434],
        "alerts": {
            "telegram": {
                "enabled": True,
                "bot_token": "<YOUR_TELEGRAM_BOT_TOKEN>",
                "chat_id": "<YOUR_TELEGRAM_CHAT_ID>",
                "admin_chat_id": "<YOUR_ADMIN_CHAT_ID>"
            },
            "thresholds": {
                "max_failed_logins_per_hour": 5,
                "max_invalid_user_logins": 3,
                "alert_on_root_login": True,
                "alert_on_unknown_ip": True
            }
        },
        "blocking": {
            "enabled": True,
            "ban_duration_hours": 48,
            "banned_file": "/var/log/vps_monitor/banned_ips.json"
        },
        "monitor": {
            "cycle_interval_seconds": 60,
            "auth_log": "/var/log/auth.log",
            "report_lines": 300
        }
    }

CFG = load_config()

# ─── Logging ─────────────────────────────────────────────────
LOG_DIR = Path("/var/log/vps_monitor")
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = LOG_DIR / "monitor.log"
except PermissionError:
    LOG_DIR  = Path.home() / "vps_monitor" / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = LOG_DIR / "monitor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("vps_shield")

# Registro file bannati
BANNED_FILE = Path(CFG.get("blocking", {}).get("banned_file", "/var/log/vps_monitor/banned_ips.json"))

# Whitelist in-memory (dinamicamente arricchita)
ACTIVE_WHITELIST = set(CFG.get("whitelist_ips", ["127.0.0.1", "::1"]))

# Stato persistente del demone
STATE = {
    "known_ports": set(CFG.get("expected_open_ports", [])),
    "failed_ips_count": defaultdict(int),
    "invalid_user_ips": defaultdict(set),
    "already_banned_ips": set(),
    "pending_bans_digest": [],
    "last_digest_time": time.time()
}

# ══════════════════════════════════════════════════════════════
#  GESTIONE WHITELIST E PERSISTENZA BLOCCHI
# ══════════════════════════════════════════════════════════════

def load_banned_ips() -> dict:
    if BANNED_FILE.exists():
        try:
            with open(BANNED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning(f"Errore lettura {BANNED_FILE}: {e}")
    return {}

def save_banned_ips(data: dict):
    try:
        BANNED_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(BANNED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"Errore scrittura {BANNED_FILE}: {e}")

# Inizializza STATE con gli IP già bannati
for _ip, _info in load_banned_ips().items():
    if _info.get("active", True):
        STATE["already_banned_ips"].add(_ip)

# ══════════════════════════════════════════════════════════════
#  TELEGRAM ALERTS
# ══════════════════════════════════════════════════════════════

def send_telegram(message: str, level: str = "INFO"):
    tg = CFG.get("alerts", {}).get("telegram", {})
    if not tg.get("enabled") or not HAS_REQUESTS:
        return

    token = tg.get("bot_token", "")
    chat_ids = [tg.get("chat_id", ""), tg.get("admin_chat_id", "")]
    chat_ids = [c for c in chat_ids if c and "INSERISCI" not in c]

    if not token or not chat_ids or "INSERISCI" in token:
        return

    icons = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️", "OK": "✅"}
    icon  = icons.get(level, "🛡️")
    ts    = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")
    text  = f"{icon} <b>VPS Shield Sicurezza</b> — {ts}\n\n{message}"

    for cid in set(chat_ids):
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": cid, "text": text, "parse_mode": "HTML"},
                timeout=8
            )
        except Exception as e:
            log.warning(f"[Telegram] Errore invio chat {cid}: {e}")

def alert(message: str, level: str = "WARNING"):
    log.warning(f"[{level}] {message}")
    send_telegram(message, level)

def flush_digest_if_needed(force: bool = False):
    """Invia un unico report Telegram consolidato con tutti i bot bloccati."""
    now = time.time()
    pending = STATE["pending_bans_digest"]
    if not pending:
        return

    # Invia se ci sono >= 5 bot bloccati oppure sono passati 30 minuti (o se forzato)
    if force or len(pending) >= 5 or (now - STATE["last_digest_time"] >= 1800):
        total_banned = len(STATE["already_banned_ips"])
        lines = []
        for item in pending[-8:]:
            lines.append(f"• <code>{item['ip']}</code> — {item['reason']}")
        
        extra = f"\n<i>...e altri {len(pending)-8} bot</i>" if len(pending) > 8 else ""
        
        msg = (
            f"🛡️ <b>REPORT BLOCCHI SHIELD FIREWALL</b>\n\n"
            f"Bloccati <b>{len(pending)} nuovi bot</b> con <code>iptables DROP</code>:\n"
            + "\n".join(lines) + extra + "\n\n"
            f"📊 <b>Totale IP malevoli bloccati:</b> {total_banned}\n"
            f"🟢 <b>Tuo accesso (whitelist):</b> Protetto e operativo"
        )
        send_telegram(msg, level="INFO")
        STATE["pending_bans_digest"] = []
        STATE["last_digest_time"] = now

# ══════════════════════════════════════════════════════════════
#  MOTORE BLOCCO FIREWALL (IPTABLES DROP)
# ══════════════════════════════════════════════════════════════

def run_cmd(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=12)
        return result.stdout.strip()
    except Exception as e:
        log.error(f"[CMD] Errore '{cmd}': {e}")
        return ""

def ban_ip(ip: str, reason: str, attempts: int = 0, is_targeted: bool = False) -> bool:
    """Blocca immediatamente l'IP attaccante con iptables DROP."""
    # 1. Controlla Whitelist
    if ip in ACTIVE_WHITELIST or ip.startswith(("127.", "10.", "192.168.", "::1")):
        log.info(f"[SHIELD] IP {ip} è in WHITELIST. Blocco annullato.")
        return False

    # 2. Verifica se già bannato
    if ip in STATE["already_banned_ips"]:
        return True

    log.warning(f"[SHIELD] BLOCCANDO IP ATTACCANTE: {ip} (Motivo: {reason}, Tentativi: {attempts})")

    # 3. Esegui comando iptables DROP all'istante
    check = run_cmd(f"iptables -C INPUT -s {ip} -j DROP 2>/dev/null; echo $?")
    if check != "0":
        run_cmd(f"iptables -I INPUT -s {ip} -j DROP")
        log.info(f"[SHIELD] Regola iptables DROP inserita per {ip}")

    # 4. Registra nel file JSON
    banned_store = load_banned_ips()
    now_str = datetime.now(timezone.utc).isoformat()
    duration = CFG.get("blocking", {}).get("ban_duration_hours", 48)

    banned_store[ip] = {
        "ip": ip,
        "reason": reason,
        "attempts": attempts,
        "banned_at": now_str,
        "duration_hours": duration,
        "active": True
    }
    save_banned_ips(banned_store)
    STATE["already_banned_ips"].add(ip)

    # 5. Gestione Notifica Intelligente (Alert immediato solo se mirato, altrimenti Digest)
    if is_targeted:
        alert(
            f"🚨 <b>ATTACCO MIRATO INTERCETTATO E BLOCCATO!</b>\n\n"
            f"<b>IP:</b> <code>{ip}</code>\n"
            f"<b>Motivo:</b> Tentativo di accesso mirato su account personale\n"
            f"<b>Tentativi:</b> {attempts}\n"
            f"<b>Azione:</b> <code>iptables DROP</code> immediato applicato.",
            level="CRITICAL"
        )
    else:
        STATE["pending_bans_digest"].append({"ip": ip, "reason": reason})
        flush_digest_if_needed()

    return True

def unban_ip(ip: str) -> bool:
    """Rimuove il blocco iptables per un IP."""
    log.info(f"[SHIELD] Sblocco manuale IP: {ip}")
    run_cmd(f"iptables -D INPUT -s {ip} -j DROP 2>/dev/null")

    banned_store = load_banned_ips()
    if ip in banned_store:
        banned_store[ip]["active"] = False
        banned_store[ip]["unbanned_at"] = datetime.now(timezone.utc).isoformat()
        save_banned_ips(banned_store)

    if ip in STATE["already_banned_ips"]:
        STATE["already_banned_ips"].remove(ip)

    alert(f"✅ IP <code>{ip}</code> sbloccato dal firewall.", level="INFO")
    return True

# ══════════════════════════════════════════════════════════════
#  ANALISI AUTH.LOG E RILEVAMENTO ATTACCHI
# ══════════════════════════════════════════════════════════════

def check_auth_log():
    auth_log = CFG["monitor"].get("auth_log", "/var/log/auth.log")
    n_lines  = CFG["monitor"].get("report_lines", 300)
    thresh   = CFG["alerts"]["thresholds"]
    max_fails = thresh.get("max_failed_logins_per_hour", 5)
    max_invalid = thresh.get("max_invalid_user_logins", 3)

    raw = run_cmd(f"tail -n {n_lines} {auth_log} 2>/dev/null")
    if not raw:
        raw = run_cmd(f"journalctl -u ssh -n {n_lines} --no-pager 2>/dev/null")

    failed_by_ip = defaultdict(int)
    invalid_users_by_ip = defaultdict(set)
    accepted_logins = []
    targeted_users_by_ip = defaultdict(set)

    # Regex patterns
    re_fail_pwd = re.compile(r'Failed password for (?:invalid user )?(\w+) from (\d+\.\d+\.\d+\.\d+)', re.IGNORECASE)
    re_invalid_user = re.compile(r'Invalid user (\w+) from (\d+\.\d+\.\d+\.\d+)', re.IGNORECASE)
    re_accepted = re.compile(r'Accepted (?:password|publickey) for (\w+) from (\d+\.\d+\.\d+\.\d+)', re.IGNORECASE)

    for line in raw.splitlines():
        # 1. Login Riusciti (Auto-Whitelist per Davide)
        m_ok = re_accepted.search(line)
        if m_ok:
            user, ip = m_ok.group(1), m_ok.group(2)
            accepted_logins.append((user, ip))
            if user in ("davide", "root") and ip not in ACTIVE_WHITELIST:
                ACTIVE_WHITELIST.add(ip)
                log.info(f"[WHITELIST] IP {ip} aggiunto dinamicamente alla Whitelist (login valido per '{user}')")

        # 2. Utenti Inesistenti
        m_inv = re_invalid_user.search(line)
        if m_inv:
            u_name, ip = m_inv.group(1), m_inv.group(2)
            invalid_users_by_ip[ip].add(u_name)
            failed_by_ip[ip] += 1
            if u_name.lower() in ("davide", "carrieri"):
                targeted_users_by_ip[ip].add(u_name)

        # 3. Password Fallite
        m_fail = re_fail_pwd.search(line)
        if m_fail:
            u_name, ip = m_fail.group(1), m_fail.group(2)
            failed_by_ip[ip] += 1
            if u_name.lower() in ("davide", "carrieri"):
                targeted_users_by_ip[ip].add(u_name)

    # 4. VALUTAZIONE ED ESECUZIONE BLOCCHI ATTIVI
    if CFG.get("blocking", {}).get("enabled", True):
        for ip, count in failed_by_ip.items():
            if ip in ACTIVE_WHITELIST:
                continue

            is_targeted = bool(targeted_users_by_ip.get(ip))
            invalid_users = invalid_users_by_ip.get(ip, set())

            if is_targeted:
                ban_ip(ip=ip, reason=f"Attacco mirato all'utente personale '{list(targeted_users_by_ip[ip])[0]}'", attempts=count, is_targeted=True)
            elif len(invalid_users) >= max_invalid or (invalid_users and count >= 3):
                ban_ip(
                    ip=ip,
                    reason=f"Bot scanning con utenti fittizi ({', '.join(sorted(invalid_users)[:3])})",
                    attempts=count,
                    is_targeted=False
                )
            elif count >= max_fails:
                ban_ip(
                    ip=ip,
                    reason=f"{count} tentativi falliti su SSH",
                    attempts=count,
                    is_targeted=False
                )

    return {
        "failed_by_ip": dict(failed_by_ip),
        "invalid_users_by_ip": {k: list(v) for k, v in invalid_users_by_ip.items()},
        "accepted_logins": accepted_logins
    }

# ══════════════════════════════════════════════════════════════
#  CHECK PORTE E RISORSE
# ══════════════════════════════════════════════════════════════

def check_open_ports():
    expected = set(CFG.get("expected_open_ports", [22, 53, 80, 443, 8000, 8550, 11434]))
    raw = run_cmd("ss -tlnp 2>/dev/null")
    open_ports = set()
    re_socket = re.compile(r'(\S+):(\d{2,5})\s+')
    for line in raw.splitlines():
        if "LISTEN" in line:
            # Ignora esplicitamente i runner interni di Ollama / llama-server
            if "llama-server" in line or "ollama" in line:
                continue
            m = re_socket.search(line)
            if m:
                addr, port_val = m.group(1), int(m.group(2))
                # Se la porta ascolta esclusivamente su loopback (127.0.0.1 o ::1), non è esposta a Internet
                if addr in ("127.0.0.1", "::1", "localhost", "127.0.0.53"):
                    continue
                open_ports.add(port_val)

    unexpected = open_ports - expected
    if unexpected:
        alert(f"🔓 <b>Porte inattese aperte sulla VPS!</b> {sorted(unexpected)}", level="WARNING")
    return {"open_ports": sorted(open_ports), "unexpected": sorted(unexpected)}

def check_system_resources():
    cpu  = run_cmd("top -bn1 | grep 'Cpu(s)' | awk '{print $2}'")
    ram  = run_cmd("free -h | awk '/^Mem:/{print $3\"/\"$2}'")
    disk = run_cmd("df -h / | awk 'NR==2{print $5\" su \"$2}'")
    return {"cpu": cpu, "ram": ram, "disk": disk}

# ══════════════════════════════════════════════════════════════
#  CICLO DI MONITORAGGIO COMPLETO
# ══════════════════════════════════════════════════════════════

def run_cycle():
    log.info("--- Scansione Shield VPS ---")
    auth_data = check_auth_log()
    ports_data = check_open_ports()
    sys_data = check_system_resources()

    total_attacks = sum(auth_data["failed_by_ip"].values())
    banned_count = len(STATE["already_banned_ips"])

    log.info(f"[Stato] Attacchi: {total_attacks} | IP Bannati: {banned_count} | Whitelist: {len(ACTIVE_WHITELIST)}")
    flush_digest_if_needed()
    return {
        "auth": auth_data,
        "ports": ports_data,
        "system": sys_data,
        "banned_count": banned_count
    }

def main():
    import argparse
    parser = argparse.ArgumentParser(description="VPS Security Shield & Auto-Ban — Simbio Ecosystem")
    parser.add_argument("--once", action="store_true", help="Esegui una sola scansione e termina")
    parser.add_argument("--ban", type=str, help="Blocca manualmente un IP attaccante")
    parser.add_argument("--unban", type=str, help="Sblocca un IP")
    parser.add_argument("--status", action="store_true", help="Mostra stato attuale dello shield")
    args = parser.parse_args()

    if args.ban:
        ban_ip(args.ban, "Blocco manuale da riga di comando CLI", 1, is_targeted=True)
        return

    if args.unban:
        unban_ip(args.unban)
        return

    if args.status:
        banned = load_banned_ips()
        print(f"\n=== SIMBIO SECURITY SHIELD STATUS ===")
        print(f"Whitelist protetta: {sorted(list(ACTIVE_WHITELIST))}")
        print(f"IP Bloccati attivi: {len([k for k, v in banned.items() if v.get('active')])}")
        for ip, info in banned.items():
            if info.get("active"):
                print(f" - {ip}: {info.get('reason')} (bannato il {info.get('banned_at')})")
        return

    if args.once:
        run_cycle()
        return

    # Modalità demone continuo
    interval = CFG.get("monitor", {}).get("cycle_interval_seconds", 60)
    log.info(f"Simbio Security Shield avviato in modalità continua (intervallo: {interval}s)")

    while True:
        try:
            run_cycle()
        except Exception as e:
            log.error(f"Eccezione nel ciclo monitor: {e}")
        time.sleep(interval)

if __name__ == "__main__":
    main()
