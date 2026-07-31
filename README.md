# 営業リスト収集システム Version 4

都道府県・市区町村・検索業種を条件に企業の公式ホームページを探し、営業対象の候補を収集するシステムです。

> **現在の開発段階: Phase 11.2.2.1（Windows Python検出）**<br>
> actions/setup-pythonを含む64bit Python 3.13の検出順とsetup smoke gateを固定します。

Windows利用者は最初に[`docs/windows_setup.md`](docs/windows_setup.md)を参照し、`setup.bat`を
実行してください。

## 動作環境

- Python 3.13
- SQLite（Python 標準ライブラリ）
- Windows を主な実行環境として想定
- Google API、Google Maps API、Places API、有料 API、有料検索、クラウド DB は使用しない

## ディレクトリ構成

```text
.
├── config/                 # 環境に依存しない既定設定
│   ├── default.yaml
│   ├── exclude_domains.txt
│   ├── industry_keywords.yaml
│   └── providers.yaml
├── data/                   # SQLite DB などの実行時データ
├── docs/                   # 設計・運用ドキュメント
│   ├── architecture.md
│   ├── phase1.md
│   ├── phase2.md
│   ├── phase3.md
│   ├── phase4.md
│   ├── phase5.md
│   ├── phase6.md
│   ├── phase7.md
│   └── phase8.md
├── input/                  # 検索条件などの入力ファイル
├── logs/                   # 実行ログ
├── output/                 # Excel / CSV などの成果物
├── src/
│   ├── crawler/            # robots、RateLimiter、Fetcher、Playwright fallback
│   ├── export/             # csv.py、excel.py
│   ├── extractor/          # JSON-LD、schema.org、会社名、住所、電話、業種
│   ├── pipeline/           # 統合モデル、1件処理、単一Worker調整
│   ├── status/             # SQLiteステータス集計（表示非依存）
│   ├── scoring/            # Domain・PageType・公式・営業対象判定
│   ├── search/             # providers、query_builder.py、result_parser.py
│   ├── storage/            # sqlite.py、progress.py
│   └── utils/              # config.py、logger.py
└── tests/
    ├── html_samples/       # 抽出テスト用の合成 HTML
    ├── integration/        # モジュール間・DB 結合テスト
    └── unit/               # 単体テスト
```

空の実行時ディレクトリには追跡用の `.gitkeep` を置いています。生成された DB、ログ、入力・出力ファイルは Git の管理対象外です。

## 開発環境のセットアップ

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
python -m ruff check .
```

ブラウザを使う検索・巡回機能は後続 Phase で実装します。その時点で必要に応じて `python -m playwright install` を実行します。

## 段階的な開発方針

1. **Phase 1:** 構成、依存関係、設定、ドキュメント、テスト基盤（完了）
2. **Phase 2:** SQLite、Progress、Logger、Resume、設定管理（完了）
3. **Phase 3:** QueryBuilder、Provider契約、Bing RSS、SearchManager（完了）
4. **Phase 4:** robots.txt、RateLimiter、Fetcher、Playwright fallback（完了）
5. **Phase 5:** 構造化データ・ページ本文からの情報抽出（完了）
6. **Phase 6:** 公式サイト判定、除外理由、営業対象スコア（完了）
7. **Phase 7:** 既存モジュールを接続する単一Workerパイプライン（完了）
8. **Phase 8:** CSV・Excel、StatusService、最小CLI（今回）
9. **Phase 9:** 収集CLI、Windowsバッチ、運用レビュー（予定）

各 Phase の終了時にレビュー、テスト、改善を行い、合意後に次の Phase へ進みます。詳細は [Architecture](docs/architecture.md) と `docs/phase*.md` を参照してください。

## 現時点で実行できること

Phase 8で利用できるCLIは`python -m src.cli status`と`python -m src.cli export`です。収集開始コマンドはまだ提供しません。ExportはSQLiteだけを読み、CrawlerやExtractorを呼びません。

## ライセンス

[MIT License](LICENSE)
