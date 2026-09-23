"""
Simbio VPS Core API & UI Server
Punto di ingresso principale:
- Serve la Web UI Mobile PWA (/ , /hardware, /console)
- Espone le API REST/SSE sicure (/v1/chat/completions, /api/v1/...)
"""
from pathlib import Path
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

import config
import core_integrity
import database
from routes.chat import router as chat_router
from routes.system import router as system_router
from routes.telegram import router as telegram_router
from routes.sessions import router as sessions_router
from routes.media import router as media_router


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("==================================================")
    print("  Simbio Core API & UI v2.0 - ONLINE")
    print(f"  Web UI:    http://{config.HOST}:{config.PORT}/")
    print(f"  API Docs:  http://{config.HOST}:{config.PORT}/docs")
    print(f"  Ollama:    {config.OLLAMA_BASE_URL}")
    print(f"  Default:   {config.DEFAULT_MODEL}")
    core_integrity.verify_core_integrity()
    print(f"  Engine:    localfirst-core/{core_integrity.get_integrity_fingerprint()} [AUTHENTIC]")
    print("==================================================")
    # Inizializzazione Database SQLite per storico conversazioni
    database.init_db()
    print("[DATABASE] SQLite simbio_chat.db inizializzato con successo.")
    yield
    print("Simbio Core API - Arresto completato.")

app = FastAPI(
    title="Simbio VPS Core API",
    version="2.0.0",
    description="API Gateway e Web UI Neurale per Simbio Ecosystem.",
    lifespan=lifespan
)

# Registrazione Middleware di Integrità e Paternità
if core_integrity.CoreIntegrityMiddleware:
    app.add_middleware(core_integrity.CoreIntegrityMiddleware)

# Configurazione CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS if "*" not in config.ALLOWED_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montaggio Cartella Static (per icone, manifest PWA, ecc.)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Inclusione dei Router API
app.include_router(chat_router)
app.include_router(system_router)
app.include_router(telegram_router)
app.include_router(sessions_router)
app.include_router(media_router)

# -------------------------------------------------------------
# ROTTE WEB UI (Mobile PWA & Browser)
# -------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, tags=["Web UI"])
async def serve_index():
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return HTMLResponse("<h1>Simbio UI in caricamento...</h1>")

@app.get("/hardware", response_class=HTMLResponse, tags=["Web UI"])
async def serve_hardware():
    hw_file = TEMPLATES_DIR / "hardware.html"
    if hw_file.exists():
        return FileResponse(hw_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return HTMLResponse("<h1>Stato Hardware non trovato.</h1>")

@app.get("/console", response_class=HTMLResponse, tags=["Web UI"])
async def serve_console():
    console_file = TEMPLATES_DIR / "console.html"
    if console_file.exists():
        return FileResponse(console_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return HTMLResponse("<h1>Console Terminale non trovata.</h1>")

@app.get("/orchestra", response_class=HTMLResponse, tags=["Web UI"])
@app.get("/neural-map", response_class=HTMLResponse, tags=["Web UI"])
async def serve_orchestra():
    orch_file = TEMPLATES_DIR / "orchestra.html"
    if orch_file.exists():
        return FileResponse(orch_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return HTMLResponse("<h1>Dashboard Orchestra non trovata.</h1>")

@app.get("/health", tags=["Salute"])
async def health_check():
    return {
        "status": "ONLINE",
        "service": "Simbio Core API & UI",
        "version": "2.0.0",
        "engine": f"localfirst-core/{core_integrity.get_integrity_fingerprint()}"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        workers=1
    )

