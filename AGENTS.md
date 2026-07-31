# Project Rules

このファイルのルールは、リポジトリ全体と今後のすべてのPhaseに適用する。

## 開発

- フェーズ単位で実装する
- 一度に完成版を書かない
- pytestを書いてから実装する
- テストが通らないコードはコミットしない

## コーディング

- 型ヒント必須
- docstring必須
- Ruff準拠
- 1行100文字以内
- 例外処理必須
- 責務ごとにモジュール分割

## テスト

- 実サイトアクセスを使うテストは禁止
- HTML fixtureのみ使用
- HTTP通信は必ずモック化
- Playwrightもモック化

## 検索

- Provider方式を維持する
- SearchManager以外からProviderを直接呼ばない
- QueryBuilder以外で検索クエリを生成しない

## クローラ

- robots.txtを必ず尊重する
- 同一ドメインの待機時間を守る
- Resume機能を壊さない

## ストレージ

- SQLiteのみ使用
- トランザクション必須
- WALモードを維持する

## 禁止

- Google API禁止
- Google Maps API禁止
- Places API禁止
- 有料API禁止
- クラウドDB禁止
- CAPTCHA回避禁止
- robots.txt無視禁止
- User-Agent偽装禁止

## Git

- 1コミット1機能
- Conventional Commitsを使用
