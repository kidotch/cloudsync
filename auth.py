"""
Dropbox OAuth2 認証
初回実行時にブラウザで認証し、トークンをローカルに保存する
"""
import json
import os
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect

TOKEN_FILE = os.path.expanduser("~/.config/cloudsync/dropbox_token.json")


def authenticate(app_key: str, app_secret: str) -> dropbox.Dropbox:
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)

    # 保存済みトークンがあれば使う
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            data = json.load(f)
        return dropbox.Dropbox(
            oauth2_refresh_token=data["refresh_token"],
            app_key=app_key,
            app_secret=app_secret,
        )

    # 初回：ブラウザで認証
    auth_flow = DropboxOAuth2FlowNoRedirect(
        app_key,
        app_secret,
        token_access_type="offline",
    )
    authorize_url = auth_flow.start()
    print("=" * 60)
    print("ブラウザで以下のURLを開いてください：")
    print(authorize_url)
    print("=" * 60)
    auth_code = input("認証コードを貼り付けてください: ").strip()

    result = auth_flow.finish(auth_code)
    with open(TOKEN_FILE, "w") as f:
        json.dump({"refresh_token": result.refresh_token}, f)
    print("認証完了。トークンを保存しました。")

    return dropbox.Dropbox(
        oauth2_refresh_token=result.refresh_token,
        app_key=app_key,
        app_secret=app_secret,
    )
