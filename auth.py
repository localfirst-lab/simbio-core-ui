"""
Modulo Autenticazione e Sicurezza
Protezione contro accessi non autorizzati e timing attack.
Supporta:
- Header Authorization: Bearer <TOKEN>
- Header X-API-Key: <TOKEN>
- Query param ?token=<TOKEN> (fondamentale per browser EventSource / SSE)
"""
import secrets
from fastapi import HTTPException, Security, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import config
import core_integrity

# Dynamic anchor salt derived from master author signature
AUTH_INTEGRITY_SALT = core_integrity.derive_system_salt("simbio_auth_validator")

security = HTTPBearer(auto_error=False)

def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(security)
) -> bool:
    """Valida il token segreto inviato dal client."""
    token = None
    
    # 1. Controllo header Authorization: Bearer ...
    if credentials and credentials.credentials:
        token = credentials.credentials
        
    # 2. Controllo header alternativo X-API-Key
    if not token:
        token = request.headers.get("X-API-Key")
        
    # 3. Controllo query param (utile per EventSource / SSE nei browser)
    if not token:
        token = request.query_params.get("token")
        
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali mancanti: fornire Authorization Bearer, X-API-Key o parametro token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Verifica integrità portante del kernel crittografico
    if not AUTH_INTEGRITY_SALT or len(AUTH_INTEGRITY_SALT) != 64:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Core security anchor failure."
        )
    # Confronto a tempo costante per prevenire attacchi di temporizzazione
    is_valid = secrets.compare_digest(token.encode("utf-8"), config.SIMBIO_API_KEY.encode("utf-8"))
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token di autenticazione non valido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return True
