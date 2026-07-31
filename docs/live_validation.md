# 少量実通信検証手順

## 実行手順

1. `setup.bat`を実行します。
2. `validate.bat`を実行します。
3. `input/search_conditions.csv`を有効な1条件だけにします。
4. 最大取得件数を3にします。
5. 最大候補処理件数を20にします。
6. `config/local.yaml`でもPlaywrightが無効であることを確認します。
7. `live_check.bat`を実行し、表示内容を読み、同意する場合だけ`Y`を入力します。
8. `output/live_validation_report.xlsx`を目視確認します。
9. `input/live_review.csv`へ`OK`、`NG`、`要確認`、`未確認`のいずれかを入力します。
10. `review_import.bat`を実行し、`live_report.bat`で精度レポートを再生成します。

非対話環境では`python -m src.cli live-check --yes`と明示しない限り通信しません。`--yes`は
安全制限を解除しません。最初は相手先の営業時間外を避け、会社ネットワークの規則を確認します。
ウイルス対策ソフトの警告、Proxy認証、OneDrive同期がある場合は社内管理者へ相談してください。

## 停止とログ確認

429、連続403、CAPTCHA表示、アクセス拒否表示が出た場合は当該ドメインを停止し、回避しません。
検索結果0件は故障とは限らず、検索サイトの仕様変更や対象サイトのrobots.txtも確認します。
HTTP本文・Cookieを含まない監査メタデータはSQLiteの`http_audit_logs`とレポートの「HTTP監査」で
確認できます。通常ログは`logs/app_YYYYMMDD.log`と`logs/launcher_*.log`です。

## 大量実行へ進む前に

少なくとも電話番号正解率95%、公式サイトprecision 90%、営業対象precision 90%、重大な誤抽出0件、
429/CAPTCHA/blockなし、Resume成功、出力重複なしを確認します。レビューが少数なら、数値を満たしても
統計的に不十分です。複数地域・業種で追加レビューし、管理者承認を得るまで上限を増やしません。
