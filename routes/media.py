"""
Router Upload Media per Simbio
Gestisce:
- Ricezione di foto da fotocamera smartphone o screenshot
- Salvataggio sicuro in static/uploads
- Restituzione dell'URL pubblico servito da FastAPI
"""
from pathlib import Path
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status

from auth import verify_token

router = APIRouter(prefix="/api/v1/media", tags=["Media"])

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "static" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB

@router.post("/upload", dependencies=[Depends(verify_token)])
async def upload_media_file(file: UploadFile = File(...)):
    """Carica un file immagine (screenshot o foto diretta) e restituisce l'URL."""
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato non supportato ({ext}). Usare JPG, PNG, WEBP o GIF."
        )

    # Genera nome univoco con UUID
    unique_filename = f"media_{uuid.uuid4().hex[:16]}{ext}"
    dest_path = UPLOADS_DIR / unique_filename

    try:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Il file supera la dimensione massima consentita di 15 MB."
            )
        
        # Scrittura su disco sicura
        dest_path.write_bytes(content)

        return {
            "status": "success",
            "url": f"/static/uploads/{unique_filename}",
            "filename": file.filename,
            "size": len(content)
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante il salvataggio del file: {str(e)}"
        )
