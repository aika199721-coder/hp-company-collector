# Phase 9: 実行アプリケーション層

## 設定統合仕様

`ApplicationConfigLoader` は default を起点に Provider、Pipeline、Scoring、業種キーワード、
除外ドメインを必須ファイルとして検証する。相対パスはプロジェクトルート基準で解決し、DB、入力、
出力、ログ、ログレベルは環境変数で上書きできる。秘密値はログへ展開しない。

## 検索条件 CSV 仕様

`input/search_conditions.csv` を UTF-8 BOM、UTF-8、CP932 の順で判定する。必須列は都道府県、
市区町村、検索業種、最大取得件数、有効である。候補上限、電話なしの計数、追加・除外語、備考は
任意である。NFKC 正規化、日本語真偽値、空行、重複、行番号付きエラーに対応する。strict は
全件拒否、lenient は正常行のみ返す。

## ApplicationFactory 設計

SQLite、Progress、PipelineStorage、Provider、SearchManager、QueryBuilder、robots、RateLimiter、
Fetcher、Extractor、Scoring、Processor、Coordinator、Export、Status、run history の生成を一か所へ
集約した。テストでは名前付き override により通信境界やサービスを差し替える。

## CollectionService の処理順

入力検証、migration、running の pending 復元、有効条件の逐次実行、条件 Summary の保存、最終
Export、Status、run 完了記録の順で処理する。条件エラー後の続行と条件ごとの Export は設定可能。
dry-run は入力検証と QueryBuilder による予定クエリ作成のみで HTTP、DB、Export を実行しない。

## collect と resume

`collect` は入力条件から開始する。`resume` は interrupted な running task を pending に戻してから
逐次処理へ合流する。処理済み URL と retry 時刻の判定は既存 Progress を維持する。

## Graceful shutdown と終了コード

SIGINT/SIGTERM handler は停止フラグだけを設定する。Coordinator は新規 claim を止め、running
復元、可能な Export、shutdown event、run 終了を一度だけ記録する。終了コードは成功 `0`、内部
エラー `1`、入力エラー `2`、一部失敗 `3`、中断 `130` である。

## Run history

`runs` は command、時刻、ファイル、条件・候補・採用・エラー集計、終了理由、バージョンを保持する。
`run_conditions` は条件 Summary、`shutdown_events` は停止理由を保持する。schema version 4 の
transaction migration で既存 DB を破壊せず追加する。

## ログ仕様

`logs/app_YYYYMMDD.log` と console へ出力し midnight rotation を行う。run_id、URL、条件 ID、
処理状態を構造化フィールドとして常に付与する。設定や認証情報そのものは出力しない。

## 次 Phase のレビュー事項

- 追加・除外検索語の検索精度
- robots 取得失敗時の fail-closed 運用
- run 単位のログ重複抑制しきい値
- Windows scripts と Playwright browser 配布方式
- 複数 Worker 導入前の claim、domain pause、shutdown の競合検証
