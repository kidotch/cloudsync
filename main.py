"""
メインエントリーポイント
使い方:
  python main.py               # 通常起動
  python main.py --setup       # 初回認証のみ実行
"""
import argparse
import logging
import os
import signal
import sys
import threading
import time

import dropbox_client as dc
import local_watcher
import state_db as db
from auth import authenticate
from sync_engine import SyncEngine

# ────────────────────────────────────────────
# 設定（環境変数 or ここに直接書く）
# ────────────────────────────────────────────
APP_KEY    = os.environ.get("DROPBOX_APP_KEY", "")
APP_SECRET = os.environ.get("DROPBOX_APP_SECRET", "")
LOCAL_ROOT = os.path.expanduser(os.environ.get("SYNC_LOCAL_ROOT", "~/sync-test"))
REMOTE_ROOT = os.environ.get("SYNC_REMOTE_ROOT", "/sync-test")
POLL_INTERVAL = int(os.environ.get("SYNC_POLL_SEC", "30"))

# ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.expanduser("~/.config/cloudsync/sync.log")),
    ],
)
logger = logging.getLogger(__name__)


def remote_poll_loop(engine: SyncEngine, dbx):
    """リモート変更をlongpollで監視するループ"""
    cursor = db.get_cursor()
    if cursor is None:
        _, cursor = dc.get_changes(dbx, None, REMOTE_ROOT)
        db.set_cursor(cursor)

    while True:
        try:
            has_changes = dc.wait_for_changes(dbx, cursor, timeout=POLL_INTERVAL)
            if has_changes:
                changes, cursor = dc.get_changes(dbx, cursor, REMOTE_ROOT)
                db.set_cursor(cursor)
                if changes:
                    engine.apply_remote_changes(changes)
        except Exception as e:
            logger.error("リモート監視エラー: %s", e)
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup", action="store_true", help="初回認証のみ実行")
    args = parser.parse_args()

    if not APP_KEY or not APP_SECRET:
        print("環境変数 DROPBOX_APP_KEY と DROPBOX_APP_SECRET を設定してください")
        sys.exit(1)

    os.makedirs(LOCAL_ROOT, exist_ok=True)
    os.makedirs(os.path.expanduser("~/.config/cloudsync"), exist_ok=True)
    db.init_db()

    dbx = authenticate(APP_KEY, APP_SECRET)
    logger.info("Dropbox 認証完了")

    if args.setup:
        print("認証完了。次回から python main.py で起動できます。")
        return

    engine = SyncEngine(dbx, LOCAL_ROOT, REMOTE_ROOT)
    engine.initial_sync()

    observer = local_watcher.start_watcher(LOCAL_ROOT, engine)

    poll_thread = threading.Thread(
        target=remote_poll_loop, args=(engine, dbx), daemon=True
    )
    poll_thread.start()

    logger.info("同期デーモン起動完了。Ctrl+C で停止。")

    def shutdown(sig, frame):
        logger.info("停止中...")
        observer.stop()
        observer.join()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
