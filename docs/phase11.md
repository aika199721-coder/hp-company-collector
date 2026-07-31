# Phase 11: 少量手動実通信検証

## 安全制限と確認フロー

通常設定と分離した`config/live_validation.yaml`で、有効条件1件、営業対象3件、候補20件、5秒待機、
Playwright無効を固定する。CLIは条件、上限、待機、Playwright、外部通信、robots尊重を表示する。
対話時の`Y`または非対話時の明示的`--yes`がなければDB作成前に終了し、通信しない。

## 停止条件

レスポンス5MiB、HTML Content-Type、redirect loop、robots拒否、429、同一ドメイン連続403、CAPTCHA、
block page、ドメイン10要求、run 50要求、15分を上限とする。停止後の回避、CAPTCHA解決、User-Agent偽装、
robots無視は行わない。監査用fetch decoratorはエラー本文を破棄してExtractorへ渡さない。

## HTTP監査

schema version 5の`http_audit_logs`へrun ID、要求/最終URL、domain、開始/終了、elapsed、status、
Content-Type/length/encoding、redirect、robots、delay、Playwright、結果分類、errorを保存する。
HTTP本文、Cookie、認証情報は列にもログにも保存しない。

## 手動レビューと精度指標

`live_validation_report.xlsx`は採用候補、要確認、除外、HTTP監査、検索結果、エラー、検証概要を持つ。
`live_review.csv`を履歴型`manual_reviews`へ追加し、自動判定を更新しない。最新レビューから法人名、店舗名、
電話、住所、業種の正解率、公式/営業対象precision、false positive/negative、要確認率を計算する。
30件未満は統計的に十分でないと明示する。

## 大量実行への移行条件

電話番号正解率95%以上、公式サイトprecision 90%以上、営業対象precision 90%以上、重大な誤抽出0件、
429/CAPTCHA/blockなし、Resume成功、出力重複なしを目安とする。少数レビューの数値達成だけでは許可せず、
複数条件で母数を増やし、監査ログと誤抽出を人がレビューしてから判断する。

## 既知の制約

streaming受信上限はContent-Lengthと実受信byteの両方を検査する。robots取得そのものと検索Provider通信の
個別監査、Proxy別の挙動、検索サイト仕様変更は追加レビューが必要である。
