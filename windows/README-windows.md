# CloudSync — Windows セットアップ手順

ノートPC（Windows）で、**ログイン中だけ常時同期**する構成。
Windowsサービスにはしない（サービスは起動直後＝ログイン前から動くため要件と逆）。
ログイン時に自動起動し、ログオフ／シャットダウンで自然に停止する。

> 前提: 同じ Dropbox アプリ（同じ `/base`）に対して、Linux機・スマホ・このWindows機が
> それぞれ独立に同期する。Dropbox がハブなので3台構成で問題ない。

---

## 0. 注意（最初に読む）

- **同じフォルダを Dropbox公式クライアントや OneDrive で二重同期しないこと。** 衝突する。
  このデーモン一本に任せる。
- 同期対象フォルダ（`SYNC_LOCAL_ROOT`）は、他の同期ソフトの管理外の場所にする。

---

## 1. Python を入れる

[python.org](https://www.python.org/downloads/) から **Python 3.10 以上** をインストール。
インストーラで **「Add python.exe to PATH」にチェック**を入れる。

確認（PowerShell）:
```powershell
python --version
```

---

## 2. リポジトリを取得して依存を入れる

```powershell
git clone https://github.com/kidotch/cloudsync $env:USERPROFILE\cloudsync
cd $env:USERPROFILE\cloudsync
pip install -r requirements.txt
```

（venv を使うなら先に `python -m venv $env:USERPROFILE\venvs\cloudsync` →
`& $env:USERPROFILE\venvs\cloudsync\Scripts\Activate.ps1` してから `pip install`）

---

## 3. 設定ファイルを置く

`%USERPROFILE%\.config\cloudsync\cloudsync.env` を作る（フォルダごと作成）:

```ini
DROPBOX_APP_KEY=<Linux機の cloudsync.env からコピー>
DROPBOX_APP_SECRET=<Linux機の cloudsync.env からコピー>
SYNC_LOCAL_ROOT=~/base
SYNC_REMOTE_ROOT=/base
SYNC_POLL_SEC=30
```

- `App Key / Secret` は Linux機の `~/.config/cloudsync/cloudsync.env` と同じ値を使う。
- `SYNC_LOCAL_ROOT=~/base` は `C:\Users\<名前>\base` に展開される。別の場所がよければフルパスで書く。
- `main.py` がこのファイルを自動で読み込む（`load_env_file`）。systemd は不要。

PowerShell でフォルダとファイルを作る例:
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.config\cloudsync" | Out-Null
notepad "$env:USERPROFILE\.config\cloudsync\cloudsync.env"
```

---

## 4. 初回認証（1回だけ）

```powershell
cd $env:USERPROFILE\cloudsync
python main.py --setup
```

表示された URL をブラウザで開く → 認証 → 出てきた**認証コードを貼り付け**。
成功すると `%USERPROFILE%\.config\cloudsync\dropbox_token.json` が保存される。

---

## 5. 動作テスト（前面で起動して確認）

```powershell
python main.py
```

初回は Dropbox `/base` の中身をまるごとダウンロードする（`SYNC_LOCAL_ROOT` に展開）。
別ウィンドウでログを見る:
```powershell
Get-Content "$env:USERPROFILE\.config\cloudsync\sync.log" -Wait -Tail 20
```
問題なければ `Ctrl+C` で止めて次へ。

---

## 6. ログイン時の自動起動を登録（ウィンドウ非表示）

1. `windows\start-cloudsync.vbs` をテキストエディタで開き、先頭の `PYTHONW` を環境に合わせて編集。
   - システムPython: `"pythonw.exe"` のまま
   - venv: `"C:\Users\<名前>\venvs\cloudsync\Scripts\pythonw.exe"`
2. `start-cloudsync.vbs` を**右クリック → ショートカットの作成**。
3. `Win + R` → `shell:startup` を実行 → 開いたスタートアップフォルダに、作ったショートカットを置く。

これでログインのたびに、**コンソール窓なし**でデーモンが起動する。

> 代替: タスクスケジューラで「ログオン時」トリガー＋「最上位の特権で実行」「ユーザーがログオンしている場合のみ」
> にしても同じ挙動にできる（リトライ設定が細かく出来る）。

---

## 7. 停止・確認

- **今すぐ止める**: タスクマネージャー → `pythonw.exe` を終了。
- **自動起動をやめる**: `shell:startup` からショートカットを削除。
- **動いているか**: `sync.log` の末尾に `list_folder/longpoll` が定期的に出ていれば常駐中。

---

## トラブル時

| 症状 | 対処 |
|---|---|
| すぐ終了する／同期されない | `python main.py` を前面で実行してエラーを見る。多くは `cloudsync.env` の設定漏れ |
| `ModuleNotFoundError: dropbox` | `pip install -r requirements.txt` を実行した Python と、`.vbs` の `PYTHONW` が同じか確認 |
| 認証エラー | `dropbox_token.json` を消して `python main.py --setup` をやり直す |
| 大文字小文字の重複 | Windows は case-insensitive なので原則起きない（Linux機側で作った同名異ケースが原因ならそちらを整理） |
