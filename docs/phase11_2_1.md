# Phase 11.2.1: Search Provider実行監査

## 対象範囲

検索Providerの実行経路、SQLite監査、live validation reportだけを補強する。Crawler、Extractor、
Scoringの判定ロジックは変更しない。通常収集とlive-checkはいずれもApplicationFactoryが生成する同一の
SearchManagerとProviderChainを利用する。

## Provider監査

`search_provider_audit`へ検索クエリと有効Providerの組み合わせを1行ずつ保存する。開始・終了日時、HTTP
status、取得・採用・重複件数、最終URL、所要時間、失敗種別とメッセージを保持し、本文、Cookie、認証情報は
保存しない。失敗は後続Providerを止めないが、403、429、CAPTCHA、blockを受けたProviderは当該run中の
後続クエリで再通信せず、`provider_stopped`として記録する。

HTML Providerは固定User-Agent `hp-company-collector/0.10`を通常のrequests headerとして送る。
ローテーション、ブラウザ偽装、ブロック回避は行わない。HTTP 200で結果が明示的に0件の場合は
`empty_results`、結果selectorが見つからない場合は`parser_mismatch`として区別する。403、429、timeout、
connection error、redirect loop、CAPTCHA、blockも個別の失敗種別にする。

## Live report

「Provider監査」シートに監査行を出力する。「検証概要」にはProvider別の実行・成功・失敗・結果・採用・
HTTP取得対象件数と、検索結果の延べ件数、正規化前提のユニークURL件数、重複数を分けて表示する。

HTTP取得前除外はエラーではない。`pages.processing_status=excluded`と`fetch_error`へ理由を保存し、
「除外」シートへURL、検索クエリ、Provider、順位、title、理由、関連性スコアを出力する。
`processing_errors`へ重複登録しないため、「除外」と「エラー」は排他的に集計される。

## 次回実通信レビュー

全有効Providerが監査シートに存在すること、Bing以外の結果または明確な失敗理由があること、除外行の検索
情報と理由が埋まること、除外数とエラー数が重複しないことを先に確認する。公式候補5件の精度評価は、
Providerの実通信経路が確認できた後に行う。
