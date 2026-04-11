import sqlite3
import os
from runtime_paths import runtime_path

def _get_owner_id():
    return int(os.environ.get("CLOUDGRAM_OWNER_ID", "0"))

DB_PATH = runtime_path("cloudgram.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER UNIQUE,
            file_name TEXT,
            file_size INTEGER,
            file_type TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_pinned BOOLEAN DEFAULT FALSE
        )
    ''')
    # Migration: add owner_id to isolate files per account
    try:
        cursor.execute("ALTER TABLE files ADD COLUMN owner_id INTEGER DEFAULT 0")
    except Exception:
        pass
    # Migration: add UNIQUE constraint on message_id if upgrading from old DB
    # (SQLite doesn't support ALTER COLUMN so we do it via a unique index)
    try:
        cursor.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_message_id ON files(message_id)'
        )
    except Exception:
        pass
    conn.commit()
    conn.close()

def add_file(message_id, file_name, file_size, file_type):
    """Insert a new file record (used by the uploader)."""
    owner_id = _get_owner_id()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO files (message_id, file_name, file_size, file_type, owner_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (message_id, file_name, file_size, file_type, owner_id))
    conn.commit()
    conn.close()

def upsert_file(message_id, file_name, file_size, file_type, uploaded_at=None):
    """
    Insert or update a file record keyed by message_id.
    Used by the startup syncer to rebuild the DB from Telegram without duplicates.
    """
    owner_id = _get_owner_id()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if uploaded_at:
        cursor.execute('''
            INSERT INTO files (message_id, file_name, file_size, file_type, uploaded_at, owner_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                file_name  = excluded.file_name,
                file_size  = excluded.file_size,
                file_type  = excluded.file_type,
                uploaded_at = excluded.uploaded_at,
                owner_id   = excluded.owner_id
        ''', (message_id, file_name, file_size, file_type, uploaded_at, owner_id))
    else:
        cursor.execute('''
            INSERT INTO files (message_id, file_name, file_size, file_type, owner_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                file_name = excluded.file_name,
                file_size = excluded.file_size,
                file_type = excluded.file_type,
                owner_id  = excluded.owner_id
        ''', (message_id, file_name, file_size, file_type, owner_id))
    conn.commit()
    conn.close()

def get_all_files():
    owner_id = _get_owner_id()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM files WHERE owner_id = ? ORDER BY uploaded_at DESC', (owner_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows
