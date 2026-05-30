"""
Dropbox API ラッパー
アップロード・ダウンロード・削除・変更検知
"""
import os
import dropbox
from dropbox.files import WriteMode, DeletedMetadata, FileMetadata
from dropbox.exceptions import ApiError


CHUNK_SIZE = 8 * 1024 * 1024  # 8MB


def to_remote_path(local_path: str, local_root: str, remote_root: str) -> str:
    rel = os.path.relpath(local_path, local_root)
    return remote_root.rstrip("/") + "/" + rel.replace(os.sep, "/")


def to_local_path(remote_path: str, local_root: str, remote_root: str) -> str:
    rel = remote_path[len(remote_root):].lstrip("/")
    return os.path.join(local_root, rel)


def upload(dbx: dropbox.Dropbox, local_path: str, remote_path: str) -> str | None:
    size = os.path.getsize(local_path)
    with open(local_path, "rb") as f:
        if size <= CHUNK_SIZE:
            meta = dbx.files_upload(f.read(), remote_path, mode=WriteMode.overwrite)
        else:
            session = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
            cursor = dropbox.files.UploadSessionCursor(session.session_id, CHUNK_SIZE)
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                remaining = size - f.tell()
                if remaining <= 0:
                    commit = dropbox.files.CommitInfo(remote_path, mode=WriteMode.overwrite)
                    meta = dbx.files_upload_session_finish(chunk, cursor, commit)
                    break
                dbx.files_upload_session_append_v2(chunk, cursor)
                cursor.offset += len(chunk)
    return meta.rev if meta else None


def download(dbx: dropbox.Dropbox, remote_path: str, local_path: str):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    _, response = dbx.files_download(remote_path)
    with open(local_path, "wb") as f:
        f.write(response.content)


def delete_remote(dbx: dropbox.Dropbox, remote_path: str):
    try:
        dbx.files_delete_v2(remote_path)
    except ApiError:
        pass


def ensure_folder(dbx: dropbox.Dropbox, remote_path: str):
    """リモートフォルダが存在しなければ作成する"""
    try:
        dbx.files_get_metadata(remote_path)
    except ApiError:
        try:
            dbx.files_create_folder_v2(remote_path)
        except ApiError:
            pass


def list_remote(dbx: dropbox.Dropbox, remote_root: str) -> list[FileMetadata]:
    ensure_folder(dbx, remote_root)
    results = []
    try:
        res = dbx.files_list_folder(remote_root, recursive=True)
        while True:
            for entry in res.entries:
                if isinstance(entry, FileMetadata):
                    results.append(entry)
            if not res.has_more:
                break
            res = dbx.files_list_folder_continue(res.cursor)
    except ApiError:
        pass
    return results


def get_changes(dbx: dropbox.Dropbox, cursor: str | None, remote_root: str):
    """変更リストを返す。cursor=None の場合は初回カーソルを取得する"""
    if cursor is None:
        ensure_folder(dbx, remote_root)
        res = dbx.files_list_folder_get_latest_cursor(remote_root, recursive=True)
        return [], res.cursor

    changes = []
    res = dbx.files_list_folder_continue(cursor)
    while True:
        changes.extend(res.entries)
        if not res.has_more:
            break
        res = dbx.files_list_folder_continue(res.cursor)
    return changes, res.cursor


def wait_for_changes(dbx: dropbox.Dropbox, cursor: str, timeout: int = 30) -> bool:
    """変更があれば True を返す（longpoll）"""
    result = dbx.files_list_folder_longpoll(cursor, timeout=timeout)
    return result.changes
