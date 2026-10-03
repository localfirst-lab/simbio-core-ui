"""
Modulo Autenticazione e Sicurezza
Protezione contro accessi non autorizzati, brute-force e timing attack.
Supporta:
- Header Authorization: Bearer <TOKEN>
- Header X-API-Key: <TOKEN>
- Query param ?token=<TOKEN> (fondamentale per browser EventSource / SSE)
- Shield Anti Brute-Force integrato su base IP
"""

import secrets
import time
from collections import defaultdict
from fastapi import HTTPException, Security, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import config

security = HTTPBearer(auto_error=False)

# Tabella in-memory per tracciare tentativi falliti per IP
# Formato: { "ip_address": [timestamp1, timestamp2, ...] }
FAILED_AUTH_LOG = defaultdict(list)
FAILED_THRESHOLD = 7       # Max 7 tentativi errati
WINDOW_SECONDS = 300       # Finestra temporale di 5 minuti
LOCKOUT_SECONDS = 900      # 15 minuti di blocco IP temporaneo per brute-force

def get_client_ip(request: Request) -> str:
    """Estrae l'indirizzo IP del client rispettando i reverse proxy (Nginx)."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"

def get_auth_error_msg(request: Request, key: str, **kwargs) -> str:
    """Restituisce il messaggio di errore di autenticazione in Italiano o Tedesco in base al client."""
    is_de = False
    lang_param = request.query_params.get("lang", "").lower()
    if lang_param.startswith("de"):
        is_de = True
    else:
        accept_lang = request.headers.get("Accept-Language", "").lower()
        if "de" in accept_lang and ("it" not in accept_lang or accept_lang.find("de") < accept_lang.find("it")):
            is_de = True

    if key == "lockout":
        rem = kwargs.get("remaining", 0)
        ip = kwargs.get("ip", "")
        if is_de:
            return f"Zu viele fehlgeschlagene Authentifizierungsversuche von IP {ip}. Bitte in {rem} Sekunden erneut versuchen."
        return f"Troppi tentativi di autenticazione falliti dall'IP {ip}. Riprova tra {rem} secondi."
    
    if key == "missing":
        if is_de:
            return "Fehlende Anmeldedaten: Bitte Authorization Bearer, X-API-Key oder Token-Parameter angeben."
        return "Credenziali mancanti: fornire Authorization Bearer, X-API-Key o parametro token."
        
    if key == "invalid":
        cur = kwargs.get("current_fails", 0)
        thresh = kwargs.get("threshold", 7)
        if is_de:
            return f"Ungültiger Authentifizierungs-Token (Versuch {cur}/{thresh})."
        return f"Token di autenticazione non valido (Tentativo {cur}/{thresh})."
        
    return "Accesso non autorizzato / Nicht autorisierter Zugriff."

def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security)
) -> bool:
    """Valida il token segreto inviato dal client con protezione anti brute-force."""
    client_ip = get_client_ip(request)
    now = time.time()

    # 1. Verifica se l'IP è temporaneamente bloccato per troppi fallimenti
    recent_fails = [t for t in FAILED_AUTH_LOG[client_ip] if now - t < WINDOW_SECONDS]
    FAILED_AUTH_LOG[client_ip] = recent_fails

    if len(recent_fails) >= FAILED_THRESHOLD:
        oldest_recent = recent_fails[0]
        remaining = int(LOCKOUT_SECONDS - (now - oldest_recent))
        if remaining > 0:
            msg = get_auth_error_msg(request, "lockout", remaining=remaining, ip=client_ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=msg,
                headers={"Retry-After": str(remaining)}
            )

    token = None
    
    # 2. Controllo header Authorization: Bearer ...
    if credentials and credentials.credentials:
        token = credentials.credentials
        
    # 3. Controllo header alternativo X-API-Key
    if not token:
        token = request.headers.get("X-API-Key")
        
    # 4. Controllo query param (per EventSource / SSE nei browser)
    if not token:
        token = request.query_params.get("token")
        
    if not token:
        # Non registriamo un fallimento per richieste semplicemente anonime,
        # ma solleviamo subito 401
        msg = get_auth_error_msg(request, "missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=msg,
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 5. Confronto a tempo costante per prevenire attacchi di temporizzazione
    is_valid = secrets.compare_digest(
        token.strip().encode("utf-8"),
        config.SIMBIO_API_KEY.strip().encode("utf-8")
    )
    
    if not is_valid:
        FAILED_AUTH_LOG[client_ip].append(now)
        current_fails = len(FAILED_AUTH_LOG[client_ip])
        msg = get_auth_error_msg(request, "invalid", current_fails=current_fails, threshold=FAILED_THRESHOLD)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=msg,
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Reset fallimenti su successo
    if client_ip in FAILED_AUTH_LOG:
        FAILED_AUTH_LOG[client_ip] = []

    return True
