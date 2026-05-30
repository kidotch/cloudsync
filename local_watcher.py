"""
watchdog によるローカルファイル変更検知
"""
import logging
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


class LocalChangeHandler(FileSystemEventHandler):
    def __init__(self, engine):
        self.engine = engine

    def on_modified(self, event):
        if not event.is_directory:
            self.engine.schedule_upload(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self.engine.schedule_upload(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self.engine.handle_local_delete(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.engine.handle_local_delete(event.src_path)
            self.engine.schedule_upload(event.dest_path)


def start_watcher(local_root: str, engine) -> Observer:
    handler = LocalChangeHandler(engine)
    observer = Observer()
    observer.schedule(handler, local_root, recursive=True)
    observer.start()
    logger.info("ローカル監視開始: %s", local_root)
    return observer
