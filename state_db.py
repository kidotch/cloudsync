"""
SQLite で同期状態を管理する
- ファイルパス・ハッシュ・リモートIDを記録
- 競合検出に使用
"""
import hashlib
import os
import sqlite3


DB_PATH = os.path.expanduser("~/.config/cloudsync/state.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS files (
            local_path  TEXT PRIMARY KEY,
            remote_path TEXT,
            local_hash  TEXT,
            remote_rev  TEXT,
            synced_at   REAL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS cursor (
            id     INTEGER PRIMARY KEY,
            value  TEXT
        )
    """)
    con.commit()
    con.close()


def get_conn():
    return sqlite3.connect(DB_PATH)


def file_hash(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_file(local_path: str) -> dict | None:
    with get_conn() as con:
        row = con.execute(
            "SELECT local_path, remote_path, local_hash, remote_rev, synced_at "
            "FROM files WHERE local_path = ?",
            (local_path,),
        ).fetchone()
    if row is None:
        return None
    return dict(zip(["local_path", "remote_path", "local_hash", "remote_rev", "synced_at"], row))


def upsert_file(local_path: str, remote_path: str, local_hash: str, remote_rev: str):
    import time
    with get_conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?, ?)",
            (local_path, remote_path, local_hash, remote_rev, time.time()),
        )
        con.commit()


def delete_file(local_path: str):
    with get_conn() as con:
        con.execute("DELETE FROM files WHERE local_path = ?", (local_path,))
        con.commit()


def get_cursor() -> str | None:
    with get_conn() as con:
        row = con.execute("SELECT value FROM cursor WHERE id = 1").fetchone()
    return row[0] if row else None


def set_cursor(value: str):
    with get_conn() as con:
        con.execute("INSERT OR REPLACE INTO cursor VALUES (1, ?)", (value,))
        con.commit()
