# Phase 11.1: 初回実通信レビュー改善

## 検索関連性

QueryBuilderは市区町村と業種を中心に、業種類義語、短縮地域名、公式語、`site:.jp`を組み合わせた
最大5クエリを生成する。類義語は`config/industry_keywords.yaml`で変更できる。live-checkでは設定の
最大3クエリ・各10結果を上限とする。

検索結果のURL、title、snippetに業種または類義語がない候補はHTTP取得前に除外する。自治体、
Wikipedia、ニュース、観光・旅行、ランキング・まとめも事前除外する。検索履歴、除外状態、理由は
SQLiteのsearch_results、pages、processing_errorsへ残す。

## 日本語encoding

encodingはContent-Typeの明示charset、BOM、meta charset、meta http-equiv、apparent encoding、
UTF-8、CP932/Shift_JISの順で決定する。暗黙のISO-8859-1は採用しない。厳密decodeに成功した候補を
選び、`æ`、`ç`、`ã`、`縺`、`繧`、`蜿`が複数ある候補は再評価する。

## CAPTCHA判定

script、CSS、URL、ライブラリ名を可視テキストから除外する。一般的な`captcha`単語だけでは止めず、
「私はロボットではありません」「画像認証」「CAPTCHAを入力」「Verify you are human」、
「Security check」「Cloudflare challenge」の可視表示だけを停止信号とする。回避処理は行わない。

## 住所・業種抽出

本文・footer住所は郵便番号または番地らしい構造を必須とし、句点、敬体、`属する`、`周囲`を含む
説明文を除外する。JSON-LD、会社概要、accessは従来の高優先度を維持する。

業種はJSON-LD、schema.org、title、h1、会社・サービスsection、本文の順で評価する。本文だけの
確定には2回以上の一致を必要とし、観光、旅行、ニュース、ランキング、まとめ、記事ページでは
本文キーワードだけで確定しない。

## 再検証

同じ「沖縄県 那覇市 美容室」の上限でlive-checkを再実行し、HTTP監査でprefetch除外理由を確認する。
GitHub Actionsはソースから配布ZIPを再生成し、`hp_company_collector_v0.10.0_windows.zip`としてArtifactへ
保存する。自動テストは合成fixtureとFake HTTPだけを使用する。
