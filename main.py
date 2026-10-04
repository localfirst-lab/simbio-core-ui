"""
Simbio VPS Core API & UI Server
Punto di ingresso principale:
- Serve la Web UI Mobile PWA (/ , /hardware, /console, /orchestra, /security)
- Espone il Service Worker (/sw.js) e il Manifest (/manifest.json) per la PWA nativa senza barra URL
- Espone le API REST/SSE sicure (/v1/chat/completions, /api/v1/system, /api/v1/security)
"""
from pathlib import Path
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

import config
import database
from routes.chat import router as chat_router
from routes.system import router as system_router
from routes.telegram import router as telegram_router
from routes.sessions import router as sessions_router
from routes.media import router as media_router
from routes.security import router as security_router


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("==================================================")
    print("  Simbio Core API & UI v2.1 - ONLINE")
    print(f"  Web UI:    http://{config.HOST}:{config.PORT}/")
    print(f"  API Docs:  http://{config.HOST}:{config.PORT}/docs")
    print(f"  Ollama:    {config.OLLAMA_BASE_URL}")
    print(f"  Default:   {config.DEFAULT_MODEL}")
    print("==================================================")
    # Inizializzazione Database SQLite per storico conversazioni
    database.init_db()
    print("[DATABASE] SQLite simbio_chat.db inizializzato con successo.")
    yield
    print("Simbio Core API - Arresto completato.")

app = FastAPI(
    title="Simbio VPS Core API",
    version="2.1.0",
    description="API Gateway e Web UI Neurale con Shield Sicurezza per Simbio Ecosystem.",
    lifespan=lifespan
)

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

# Inclusione dei Router API protetti da Pydantic
app.include_router(chat_router)
app.include_router(system_router)
app.include_router(telegram_router)
app.include_router(sessions_router)
app.include_router(media_router)
app.include_router(security_router)

# -------------------------------------------------------------
# ROTTE PWA ESSENZIALI (PER NASCONDERE L'URL SULLO SMARTPHONE)
# -------------------------------------------------------------
@app.get("/sw.js", tags=["PWA"])
async def serve_sw():
    """Serve il Service Worker alla radice per consentire lo scope globale."""
    sw_file = STATIC_DIR / "sw.js"
    if sw_file.exists():
        return FileResponse(
            sw_file,
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Service-Worker-Allowed": "/"
            }
        )
    return HTMLResponse("// Service Worker non trovato", status_code=404)

@app.get("/manifest.json", tags=["PWA"])
async def serve_manifest():
    """Serve il Web App Manifest alla radice."""
    manifest_file = STATIC_DIR / "manifest.json"
    if manifest_file.exists():
        return FileResponse(
            manifest_file,
            media_type="application/manifest+json",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    return HTMLResponse("{}", status_code=404)

# -------------------------------------------------------------
# ROTTE WEB UI (Mobile PWA & Browser)
# -------------------------------------------------------------
def render_template(file_path: Path) -> HTMLResponse:
    """Carica il template e inietta la chiave API configurata sul server (.env)."""
    if not file_path.exists():
        return HTMLResponse("<h1>Template non trovato</h1>", status_code=404)
    content = file_path.read_text(encoding="utf-8")
    injected_token = getattr(config, "SIMBIO_API_KEY", "")
    content = content.replace("{{SIMBIO_INJECTED_TOKEN}}", injected_token)
    return HTMLResponse(content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

@app.get("/", response_class=HTMLResponse, tags=["Web UI"])
async def serve_index():
    return render_template(TEMPLATES_DIR / "index.html")

@app.get("/hardware", response_class=HTMLResponse, tags=["Web UI"])
async def serve_hardware():
    return render_template(TEMPLATES_DIR / "hardware.html")

@app.get("/console", response_class=HTMLResponse, tags=["Web UI"])
async def serve_console():
    return render_template(TEMPLATES_DIR / "console.html")

@app.get("/orchestra", response_class=HTMLResponse, tags=["Web UI"])
@app.get("/neural-map", response_class=HTMLResponse, tags=["Web UI"])
async def serve_orchestra():
    return render_template(TEMPLATES_DIR / "orchestra.html")

@app.get("/security", response_class=HTMLResponse, tags=["Web UI"])
async def serve_security():
    return render_template(TEMPLATES_DIR / "security.html")

@app.get("/health", tags=["Salute"])
async def health_check():
    return {
        "status": "ONLINE",
        "service": "Simbio Core API & UI",
        "version": "2.1.0",
        "shield": "ACTIVE"
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        workers=1
    )
