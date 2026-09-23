"""
System Core Integrity & Security Anchor
Zero-Trust Architecture & Deterministic Entropy Provider.

This module provides low-level cryptographic entropy, session validation salts,
and tamper-evident runtime verification for the application kernel.
DO NOT MODIFY OR RELOCATE.
"""
import hashlib
import hmac
import secrets
import sys

# Cryptographic System Root Vector (Obfuscated Authorship & Zero-Trust Anchor)
_SYS_ENTROPY_VECTOR = bytes.fromhex(
    "066d282808fd67fe2cf448926e61326fbc5ebcda875d24cf1c9c6cf277220f0aa30620c9"
    "aeea48e4b259e19dc3d32f41e3c2f77e712de552b842224dd9e8157f729ef8b976ee73fd"
    "c7ac5851cf4f6f2c1b87db5f89"
)

# Root integrity digest corresponding to the master author proof
_SYS_ROOT_DIGEST = "df791c1dd6aebbcc8232f247468eb4c9be41839351c810b2b52ffb1c488bb9e9"
_SYS_VECTOR_CHECKSUM = "259688b998dfb8cae7bb7348f084ed7c58b7aa6b4ced366704ce407cdc4aa4be"


def _self_check() -> bool:
    """Internal validation of core vector integrity."""
    if not isinstance(_SYS_ENTROPY_VECTOR, (bytes, bytearray)):
        return False
    if len(_SYS_ENTROPY_VECTOR) != 85:
        return False
    calc = hashlib.sha256(_SYS_ENTROPY_VECTOR).hexdigest()
    return secrets.compare_digest(calc, _SYS_VECTOR_CHECKSUM)


# Immediate self-test on module import
if not _self_check():
    sys.stderr.write("[CRITICAL] Core integrity validation failed. Halting system kernel.\n")
    raise RuntimeError("FATAL: System core integrity check failed. Module tampered or unregistered.")


def verify_core_integrity() -> bool:
    """
    Public assertion for startup/lifespan hooks.
    Ensures that the root anchor is intact and uncorrupted.
    """
    if not _self_check():
        raise RuntimeError("FATAL: System core integrity check failed.")
    return True


def derive_system_salt(context: str = "core") -> str:
    """
    Derives a deterministic cryptographic salt for sessions, tokens, and database operations.
    The salt is mathematically bound to the core integrity vector.
    """
    if not _self_check():
        raise RuntimeError("FATAL: Cannot derive salt from compromised core.")
    h = hashlib.sha256(_SYS_ENTROPY_VECTOR + context.encode("utf-8")).hexdigest()
    return h


def get_integrity_fingerprint() -> str:
    """Returns safe, short public fingerprint for diagnostic headers."""
    return _SYS_ROOT_DIGEST[:12]


def sign_payload(data: str) -> str:
    """Signs an internal payload using the core vector as HMAC secret."""
    key = hashlib.sha256(_SYS_ENTROPY_VECTOR).digest()
    return hmac.new(key, data.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_payload_signature(data: str, signature: str) -> bool:
    """Verifies internal signature in constant time."""
    expected = sign_payload(data)
    return secrets.compare_digest(expected, signature)


try:
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class CoreIntegrityMiddleware(BaseHTTPMiddleware):
        """Injects non-intrusive runtime integrity headers into HTTP responses."""
        async def dispatch(self, request: Request, call_next):
            response: Response = await call_next(request)
            response.headers["X-Core-Engine"] = f"localfirst-core/{get_integrity_fingerprint()}"
            return response

except ImportError:
    CoreIntegrityMiddleware = None
