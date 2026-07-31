# Phase 11.2.2: Windows setup固定版

## 正式な配布入口

`setup.bat`、`validate.bat`、`live_check.bat`と、それらが呼ぶ`setup.ps1`、`common.ps1`を
`setupfix11.2.2-v1`として固定する。BATは`%~dp0`からプロジェクトルートを解決し、PowerShellは
Windows PowerShell 5.1互換のUTF-8 BOM・CRLFで配布する。日本語、空白、括弧、OneDrive相当のパスを
Windows CIでsmoke testする。

## setupの失敗表示

通常のダブルクリックでは成功・失敗にかかわらず`Press any key to continue`を表示して画面を保持する。
失敗時は終了コード、概要、`logs`の場所を表示する。成功時はセットアップ完了と`validate.bat`の案内を
表示する。CIと親プロセスは`--no-pause`または`HPCC_NO_PAUSE=1`を使用できる。

BATは最初に`Unblock-File`とPowerShell構文確認を実施する。setup.ps1を読み取れない場合だけ
`scripts/windows/setup_fallback.py`をPython 3.13で実行し、管理者権限やExecutionPolicy変更を要求しない。

## 回帰防止

PowerShellのBOM・CRLF、固定marker、`cmdcmdline`と`^&`の不存在、bit数確認の引用、native stderr、整数の
終了コード、pause表示、fallback、mappingproxyを含むSummary保存をOfflineテストで検証する。

## Artifact gate

配布ZIP内の全BAT・PowerShell・PythonファイルはsourceとのSHA256一致を検証する。setup関連ファイルは
marker、BOM、CRLF、旧ロジック不存在も検証する。Windows / Python 3.13のsetup smoke testでは、ZIPを
4種類のパスへ展開し、setup、validate、setup再実行がすべて終了コード0になるまでrelease Artifactを
公開しない。
