# cloudsync

Dropbox のリアルタイム同期クライアント。ログインなし・常時同期対応。

## セットアップ

### 1. 依存ライブラリのインストール

```bash
python3 -m venv venv
source venv/bin/activate
pip install dropbox watchdog
```

### 2. Dropbox App の作成

1. https://www.dropbox.com/developers/apps でアプリを作成
2. Permissions タブで以下を有効化：
   - `files.metadata.read/write`
   - `files.content.read/write`
3. App key と App secret を控える

### 3. 初回認証

```bash
DROPBOX_APP_KEY=your_key \
DROPBOX_APP_SECRET=your_secret \
SYNC_LOCAL_ROOT=/path/to/local \
SYNC_REMOTE_ROOT=/dropbox/path \
python main.py --setup
```

### 4. 起動

```bash
DROPBOX_APP_KEY=your_key \
DROPBOX_APP_SECRET=your_secret \
SYNC_LOCAL_ROOT=/path/to/local \
SYNC_REMOTE_ROOT=/dropbox/path \
python main.py
```

## 環境変数

| 変数 | 説明 | デフォルト |
|---|---|---|
| `DROPBOX_APP_KEY` | Dropbox App key | 必須 |
| `DROPBOX_APP_SECRET` | Dropbox App secret | 必須 |
| `SYNC_LOCAL_ROOT` | ローカル同期フォルダ | 必須 |
| `SYNC_REMOTE_ROOT` | Dropbox 上のパス | 必須 |
| `SYNC_POLL_SEC` | longpoll タイムアウト秒 | 30 |

## systemd サービス（Linux / ログインなし常時起動）

```bash
# 環境変数ファイルを作成
sudo cp service/cloudsync.env.example /etc/cloudsync.env
sudo vi /etc/cloudsync.env  # 値を編集

# サービスを登録
sudo cp service/cloudsync.service /etc/systemd/system/
sudo systemctl enable cloudsync
sudo systemctl start cloudsync
```

## 動作

- ローカルのファイル変更を即時検知 → Dropbox にアップロード（5秒デバウンス）
- Dropbox の変更を longpoll で検知 → ローカルにダウンロード
- 両方が変更された場合は競合コピーを自動生成
