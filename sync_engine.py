"""
同期エンジン
- ローカル変更 → アップロード
- リモート変更 → ダウンロード
- 競合検出 → 競合コピー生成
"""
import logging
import os
import threading
import time
from datetime import datetime

import dropbox
from dropbox.files import DeletedMetadata, FileMetadata

import dropbox_client as dc
import state_db as db

logger = logging.getLogger(__name__)


EXCLUDE_PREFIXES = (".obsidian/",)

def should_exclude(local_root: str, path: str) -> bool:
    rel = os.path.relpath(path, local_root).replace(os.sep, "/")
    return any(rel.startswith(p) for p in EXCLUDE_PREFIXES)


def conflict_path(local_path: str) -> str:
    base, ext = os.path.splitext(local_path)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"{base} (競合コピー {ts}){ext}"


class SyncEngine:
    def __init__(self, dbx: dropbox.Dropbox, local_root: str, remote_root: str):
        self.dbx = dbx
        self.local_root = local_root
        self.remote_root = remote_root
        self._debounce_timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()
        self._downloading: set[str] = set()  # ダウンロード中のパスを記録

    # ────────────────────────────────────────────
    # ローカル → リモート
    # ────────────────────────────────────────────

    def schedule_upload(self, local_path: str, delay: float = 5.0):
        """デバウンス付きアップロード予約"""
        if should_exclude(self.local_root, local_path):
            return
        # ダウンロード中のファイルはアップロードしない
        if local_path in self._downloading:
            return
        with self._lock:
            if local_path in self._debounce_timers:
                self._debounce_timers[local_path].cancel()
            t = threading.Timer(delay, self._do_upload, args=[local_path])
            self._debounce_timers[local_path] = t
            t.start()

    def _do_upload(self, local_path: str):
        with self._lock:
            self._debounce_timers.pop(local_path, None)

        if not os.path.exists(local_path):
            return
        if os.path.isdir(local_path):
            return

        remote_path = dc.to_remote_path(local_path, self.local_root, self.remote_root)
        current_hash = db.file_hash(local_path)
        record = db.get_file(local_path)

        # 内容が変わっていなければスキップ
        if record and record["local_hash"] == current_hash:
            return

        # 競合チェック：リモートが自分の知らない rev になっていたら競合
        if record:
            try:
                meta = self.dbx.files_get_metadata(remote_path)
                if isinstance(meta, FileMetadata) and meta.rev != record["remote_rev"]:
                    # 競合 → ローカルを競合コピーとしてアップロード
                    conflict = conflict_path(local_path)
                    logger.warning("競合検出: %s → %s", local_path, conflict)
                    os.rename(local_path, conflict)
                    rev = dc.upload(self.dbx, conflict,
                                    dc.to_remote_path(conflict, self.local_root, self.remote_root))
                    db.upsert_file(conflict,
                                   dc.to_remote_path(conflict, self.local_root, self.remote_root),
                                   db.file_hash(conflict), rev or "")
                    # リモートの最新版をローカルにダウンロード
                    dc.download(self.dbx, remote_path, local_path)
                    db.upsert_file(local_path, remote_path, db.file_hash(local_path), meta.rev)
                    return
            except Exception:
                pass

        logger.info("アップロード: %s → %s", local_path, remote_path)
        try:
            rev = dc.upload(self.dbx, local_path, remote_path)
            db.upsert_file(local_path, remote_path, current_hash, rev or "")
        except Exception as e:
            logger.error("アップロード失敗: %s: %s", local_path, e)

    def handle_local_delete(self, local_path: str):
        record = db.get_file(local_path)
        if not record:
            return
        logger.info("リモート削除: %s", record["remote_path"])
        try:
            dc.delete_remote(self.dbx, record["remote_path"])
            db.delete_file(local_path)
        except Exception as e:
            logger.error("リモート削除失敗: %s: %s", local_path, e)

    # ────────────────────────────────────────────
    # リモート → ローカル
    # ────────────────────────────────────────────

    def apply_remote_changes(self, changes: list):
        for entry in changes:
            local_path = dc.to_local_path(entry.path_lower, self.local_root, self.remote_root)

            if isinstance(entry, DeletedMetadata):
                if os.path.exists(local_path):
                    logger.info("ローカル削除: %s", local_path)
                    os.remove(local_path)
                db.delete_file(local_path)

            elif isinstance(entry, FileMetadata):
                record = db.get_file(local_path)

                # 自分のアップロード通知はスキップ（ダウンロード不要）
                if record and entry.rev == record["remote_rev"]:
                    continue

                if record and os.path.exists(local_path):
                    current_hash = db.file_hash(local_path)
                    # ローカルも変わっていたら競合
                    if current_hash != record["local_hash"]:
                        logger.warning("競合検出（リモート更新）: %s", local_path)
                        conflict = conflict_path(local_path)
                        os.rename(local_path, conflict)
                        db.upsert_file(conflict,
                                       dc.to_remote_path(conflict, self.local_root, self.remote_root),
                                       db.file_hash(conflict), "")

                logger.info("ダウンロード: %s → %s", entry.path_lower, local_path)
                try:
                    self._downloading.add(local_path)
                    dc.download(self.dbx, entry.path_lower, local_path)
                    db.upsert_file(local_path, entry.path_lower,
                                   db.file_hash(local_path), entry.rev)
                except Exception as e:
                    logger.error("ダウンロード失敗: %s: %s", local_path, e)
                finally:
                    # 少し待ってからフラグを解除（watchdog イベントが落ち着くまで）
                    threading.Timer(3.0, self._downloading.discard, args=[local_path]).start()

    # ────────────────────────────────────────────
    # 初回フルスキャン
    # ────────────────────────────────────────────

    def initial_sync(self):
        logger.info("初回同期開始: %s ↔ %s", self.local_root, self.remote_root)

        # リモートのファイルを全取得
        remote_files = {m.path_lower: m for m in dc.list_remote(self.dbx, self.remote_root)}

        # ローカルのファイルを全取得
        local_files = {}
        for root, _, files in os.walk(self.local_root):
            for f in files:
                lp = os.path.join(root, f)
                if should_exclude(self.local_root, lp):
                    continue
                rp = dc.to_remote_path(lp, self.local_root, self.remote_root).lower()
                local_files[rp] = lp

        # リモートにあってローカルにない → ダウンロード
        for rp, meta in remote_files.items():
            lp = dc.to_local_path(rp, self.local_root, self.remote_root)
            record = db.get_file(lp)
            if not os.path.exists(lp):
                logger.info("初回DL: %s", rp)
                dc.download(self.dbx, rp, lp)
                db.upsert_file(lp, rp, db.file_hash(lp), meta.rev)
            elif not record or record["remote_rev"] != meta.rev:
                self._do_upload(lp)

        # ローカルにあってリモートにない → アップロード
        for rp, lp in local_files.items():
            if rp not in remote_files:
                logger.info("初回UP: %s", lp)
                self._do_upload(lp)

        logger.info("初回同期完了")
