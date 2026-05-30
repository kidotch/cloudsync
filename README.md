# cloudsync

Dropbox のリアルタイム同期クライアント。

- ローカル変更を即時検知してアップロード（5秒デバウンス）
- Dropbox の変更を longpoll で検知してダウンロード
- 競合時は競合コピーを自動生成

## セットアップ

### 1. 依存ライブラリのインストール

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install dropbox watchdog
```

### 2. Dropbox App の作成

1. https://www.dropbox.com/developers/apps でアプリを作成
2. Permissions タブで以下を有効化して Submit：
   - `files.metadata.read` / `files.metadata.write`
   - `files.content.read` / `files.content.write`
3. App key と App secret を控える

### 3. 初回認証

```bash
DROPBOX_APP_KEY=your_key \
DROPBOX_APP_SECRET=your_secret \
SYNC_LOCAL_ROOT=/path/to/local \
SYNC_REMOTE_ROOT=/dropbox/path \
python main.py --setup
```

### 4. 手動起動

```bash
DROPBOX_APP_KEY=your_key \
DROPBOX_APP_SECRET=your_secret \
SYNC_LOCAL_ROOT=/path/to/local \
SYNC_REMOTE_ROOT=/dropbox/path \
python main.py
```

## 環境変数

| 変数 | 説明 |
|---|---|
| `DROPBOX_APP_KEY` | Dropbox App key（必須） |
| `DROPBOX_APP_SECRET` | Dropbox App secret（必須） |
| `SYNC_LOCAL_ROOT` | ローカル同期フォルダ（必須） |
| `SYNC_REMOTE_ROOT` | Dropbox 上のパス（必須） |
| `SYNC_POLL_SEC` | longpoll タイムアウト秒（デフォルト: 30） |

---

## 常駐起動の設定

### Linux：PC起動時から常時同期（ログイン不要）

```bash
# 環境変数ファイルを作成
sudo cp service/cloudsync.env.example /etc/cloudsync.env
sudo vi /etc/cloudsync.env  # 値を入力

# サービスを登録
sudo cp service/cloudsync.service /etc/systemd/system/
sudo systemctl enable cloudsync
sudo systemctl start cloudsync
```

### Windows：ログイン時に自動起動

スタートアップフォルダ（`Win+R` → `shell:startup`）に以下の内容の `.bat` ファイルを置く：

```bat
@echo off
set DROPBOX_APP_KEY=your_key
set DROPBOX_APP_SECRET=your_secret
set SYNC_LOCAL_ROOT=C:\Users\yourname\base
set SYNC_REMOTE_ROOT=/base
start /B pythonw C:\path\to\cloudsync\main.py
```

`pythonw` を使うとターミナル画面が出ずにバックグラウンドで起動します。

### macOS：ログイン時に自動起動

`~/Library/LaunchAgents/com.cloudsync.plist` を作成：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.cloudsync</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/venv/bin/python</string>
    <string>/path/to/cloudsync/main.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>DROPBOX_APP_KEY</key><string>your_key</string>
    <key>DROPBOX_APP_SECRET</key><string>your_secret</string>
    <key>SYNC_LOCAL_ROOT</key><string>/Users/yourname/base</string>
    <key>SYNC_REMOTE_ROOT</key><string>/base</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.cloudsync.plist
```
