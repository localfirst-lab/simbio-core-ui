"""
Modulo Database SQLite per Simbio Core
Gestisce in modo asincrono/thread-safe:
- Storico sessioni di chat
- Messaggi per ogni sessione
- Operazioni di creazione, rinomina, cancellazione ed esportazione
"""
import sqlite3
from pathlib import Path
import uuid
import datetime
from typing import List, Dict, Optional, Any

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "simbio_chat.db"

def get_db_connection() -> sqlite3.Connection:
    """Restituisce una connessione al database SQLite con supporto Row e Foreign Keys."""
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db():
    """Inizializza le tabelle del database se non esistono."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    media_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);")
            
            # Migrazione leggera: aggiunge la colonna media_url se il DB esisteva già
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(messages);")
            cols = [row["name"] for row in cursor.fetchall()]
            if "media_url" not in cols:
                conn.execute("ALTER TABLE messages ADD COLUMN media_url TEXT;")
    finally:
        conn.close()

def list_sessions() -> List[Dict[str, Any]]:
    """Restituisce l'elenco di tutte le sessioni ordinate dalla più recente alla più vecchia."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.title, s.created_at, s.updated_at, COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON s.id = m.session_id
            GROUP BY s.id
            ORDER BY s.updated_at DESC;
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def create_session(session_id: Optional[str] = None, title: Optional[str] = None) -> str:
    """Crea una nuova sessione e ne restituisce l'ID."""
    new_id = session_id or str(uuid.uuid4())
    session_title = title.strip() if title and title.strip() else "Nuova Conversazione"
    now = datetime.datetime.utcnow().isoformat()

    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (new_id, session_title, now, now)
            )
        return new_id
    finally:
        conn.close()

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Restituisce i dati della sessione specificata."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, created_at, updated_at FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def rename_session(session_id: str, new_title: str) -> bool:
    """Rinomina una sessione."""
    clean_title = new_title.strip()
    if not clean_title:
        return False
    now = datetime.datetime.utcnow().isoformat()
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                (clean_title, now, session_id)
            )
            return cursor.rowcount > 0
    finally:
        conn.close()

def delete_session(session_id: str) -> bool:
    """Elimina una sessione e tutti i suoi messaggi."""
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0
    finally:
        conn.close()

def get_session_messages(session_id: str) -> List[Dict[str, Any]]:
    """Restituisce tutti i messaggi associati a una sessione in rigoroso ordine cronologico."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, session_id, role, content, media_url, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def save_message(session_id: str, role: str, content: str, auto_title_if_first: bool = True, media_url: Optional[str] = None) -> int:
    """Salva un messaggio nella sessione specificata e aggiorna updated_at della sessione."""
    clean_content = content.strip()
    now = datetime.datetime.utcnow().isoformat()
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title FROM sessions WHERE id = ?", (session_id,))
            session = cursor.fetchone()
            
            # Estrai la prima riga del messaggio utente per generare un titolo pulito
            first_line = clean_content.splitlines()[0].strip() if clean_content else ""
            if role == "user" and first_line:
                clean_title = (first_line[:38].rstrip() + "...") if len(first_line) > 38 else first_line
            elif role == "user" and media_url:
                clean_title = "Immagine Allegata"
            else:
                clean_title = "Nuova Conversazione"

            if not session:
                conn.execute(
                    "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (session_id, clean_title, now, now)
                )
            else:
                # Se è il primo messaggio utente e il titolo è ancora generico, assegna la domanda come titolo
                if auto_title_if_first and role == "user" and session["title"] in ["Nuova Conversazione", "Neuer Chat", "New Conversation", "Nuova Chat"]:
                    conn.execute(
                        "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
                        (clean_title, now, session_id)
                    )
                else:
                    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))

            ins_cursor = conn.execute(
                "INSERT INTO messages (session_id, role, content, media_url, created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, clean_content, media_url, now)
            )
            return ins_cursor.lastrowid
    finally:
        conn.close()
