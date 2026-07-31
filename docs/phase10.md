# Phase 10: Windows社内配布

## 配布構成と責務

リポジトリ直下のBATは`%~dp0`基準でPowerShellを呼び、終了コードと利用者向け表示だけを担う。
`scripts/windows/common.ps1`はルート、UTF-8、Python検出、ログ、例外、pauseを共通化する。各PS1は
CLI接続を担い、収集・抽出・スコアリングロジックを持たない。

## setup処理順と再セットアップ

実行フォルダ作成、Python 3.13/bit数確認、`.venv`作成、pip更新、requirements導入、任意Chromium、
設定確認、未作成時だけ入力sampleをコピー、CLI validate、結果表示の順である。ログは
`logs/setup_YYYYMMDD_HHMMSS.log`へ保存する。再実行時も`.venv`を再利用し、入力とlocal設定を
上書きしない。Pythonは`.venv`、`py -3.13`、`python`、`python3`の順で検査し、3.13以外は拒否する。

## Playwright任意化

`crawler.playwright.enabled`の既定値はfalse。falseではbrowserを導入せず、trueの場合だけChromiumを
導入する。失敗は警告としてrequests基本経路を残す。他browserは無条件に導入しない。

## ログとdiagnostics

ランチャーログは`logs/launcher_*.log`、setupは`logs/setup_*.log`へ画面内容とstack traceを残す。
診断はOS、Python、bit数、venv、pip、依存、Playwright、設定/input/DB、schema、書込可否、パス特性、
直近ログとrun状態だけを`logs/diagnostics_*.txt`へ保存する。Cookie、HTTP本文、企業情報は保存しない。

## 配布ZIP

`scripts/build_release.py`は`dist/hp_company_collector_v0.10.0_windows.zip`を生成する。固定ルート配下に
実行コード、配布設定、sample、Windows scripts、BAT、requirements、README、Windows文書、VERSION、
空のruntimeフォルダを含める。.git、CI、venv、cache、tests、DB、ログ、出力、実入力、local設定は除外。
生成後に必須・禁止項目、展開、VERSION、日本語・空白・括弧付き一時パスを検査する。

## バージョン・アンインストール・制約

VERSIONを単一情報源としてCLIとRun Historyが参照する。アンインストールは必要な出力を退避し、
配布フォルダを削除する。管理者権限なしのため会社ポリシー、OneDrive lock、Excel lock、Proxy、
ウイルス対策製品により導入や置換が失敗する場合がある。

`requires-python = ">=3.13,<3.14"`を正式な配布条件とする。requests 2.32系、BeautifulSoup 4.12系、
openpyxl 3.1系、PyYAML 6系、Playwright 1.50系をPython 3.13 CIで導入・offline testする。
互換性回帰の検出用にPython 3.12も同じoffline test matrixへ残し、Windows/Ubuntu x64で検証する。

## Phase 11レビュー

利用者承認下でrobots、待機、検索規約を確認した少量の実通信検証、Proxy環境、Playwright fallback、
長時間resume、OneDrive/Excel lock時の運用手順を検証する。自動テストでは実サイト通信を行わない。
