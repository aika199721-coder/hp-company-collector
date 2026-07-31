# Windows 10 / 11 利用手順

## 最短手順

1. ZIPを日本語・空白・括弧を含んでもよい書込み可能なフォルダへ解凍します。
2. `setup.bat`をダブルクリックします。管理者として実行する必要はありません。
3. `input/search_conditions.csv`をExcelまたはテキストエディタで編集します。
4. `validate.bat`を実行します。
5. `collect.bat`を実行します。
6. `status.bat`で進行状況を確認します。
7. 中断またはPC再起動後は`resume.bat`を実行します。
8. 必要なら`export.bat`でCSV・Excelを再生成します。
9. 困った場合は`diagnostics.bat`を実行し、生成された診断ファイルを管理者へ渡します。

## Python

Python公式サイトからPython 3.13の64bit版をユーザー単位でインストールしてください。Pythonが
見つからない場合やMicrosoft Storeが開く場合は、Windows設定の「アプリ実行エイリアス」で
`python.exe`と`python3.exe`を無効にし、公式版を入れ直します。Python 3.12など別バージョンを
setupが誤って利用することはありません。

## トラブルシューティング

- **黒い画面が一瞬で閉じた**: `logs/setup_*.log`または`logs/launcher_*.log`を確認します。
  ターミナルからBATを実行すると詳細も確認できます。
- **PowerShell実行ポリシーエラー**: BATはプロセス限定の`-ExecutionPolicy Bypass`を使います。
  会社のポリシーで禁止される場合は管理部門へ相談し、全体設定は変更しないでください。
- **OneDrive同期中**: 同期完了を待つか、同期対象外のローカルフォルダへ移動してください。
- **Excelが出力を開いている**: Excelを閉じてから`export.bat`を再実行してください。安全な置換が
  できない場合、既存の正常ファイルは維持されます。
- **SQLite**: DBファイルをExcelで直接開いたり編集したりしないでください。
- **再セットアップ**: `setup.bat`は再実行できます。入力CSVと`config/local.yaml`を上書きしません。
- **アンインストール**: 必要な出力を退避後、解凍したフォルダ全体を削除します。

## Playwrightと利用上の注意

標準はrequestsのみで、`crawler.playwright.enabled: false`です。Playwrightを使わない限りChromiumは
導入されません。有効化する場合もChromiumだけを導入し、失敗時はrequestsで継続できます。
Google API、有料API、クラウドDBを使わない範囲は無料ですが、通信費やPC費用は利用者負担です。
検索サイトや対象サイトの仕様変更により取得できなくなる可能性があります。robots.txtを尊重し、
待機時間を短くして大量アクセスを行わないでください。
