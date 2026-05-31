' ============================================================
'  CloudSync 起動ランチャ（Windows / ログイン中のみ常駐）
' ------------------------------------------------------------
'  コンソール窓を出さずに pythonw でデーモンを起動する。
'  shell:startup にこのファイル（のショートカット）を置くと、
'  ログイン時に自動起動し、ログオフ／シャットダウンで停止する。
'  （= Windowsサービスにはしない＝ログイン中だけ常時同期）
'
'  使い方:
'    1. 下の PYTHONW を自分の環境に合わせて書き換える
'         システムPython : "pythonw.exe"
'         venv を使う場合 : "C:\Users\<名前>\venvs\cloudsync\Scripts\pythonw.exe"
'    2. README-windows.md の手順でセットアップ後、
'       Win+R → shell:startup にこの .vbs のショートカットを置く
' ============================================================

PYTHONW = "pythonw.exe"

Dim fso, scriptDir, repoDir, mainPy, sh
Set fso = CreateObject("Scripting.FileSystemObject")
' この .vbs は <repo>\windows\ に置かれる想定 → 親フォルダがリポジトリ直下
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
repoDir   = fso.GetParentFolderName(scriptDir)
mainPy    = repoDir & "\main.py"

Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = repoDir
' 第2引数 0 = ウィンドウ非表示 / 第3引数 False = 完了を待たずに抜ける
sh.Run """" & PYTHONW & """ """ & mainPy & """", 0, False
