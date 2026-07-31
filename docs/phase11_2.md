# Phase 11.2: Search Provider Chain

## 対象範囲

検索Providerだけを改善し、Extractor、Scoring、Crawlerの責務は変更しない。ProviderはSearchManagerの
内側にあるProviderChainからのみ呼び出す。

## Chain順序

既定順はBing RSS、DuckDuckGo HTML、Brave Search HTML、Mojeek HTMLである。SearXNGは運用者が
`base_url`を設定して有効化した場合だけ使う。Google API、有料APIは使用しない。個別Provider失敗時は
次Providerへ進み、全Providerの正常結果を統合する。

## 統合スコア

HTTP(S) URLをscheme、host、既定port、末尾slash、fragmentについて正規化し、同一URLは1件にする。
同じURLが複数Providerにある場合は、Provider priority、Provider内取得順位、検索語がtitle・snippet・
URLに現れる割合からchain scoreを計算し、最も強い結果を保持する。最終結果もchain score順に返す。

## 設定と検証

`config/providers.yaml`でenabledとpriorityを変更できる。HTML parserテストはローカルfixtureだけを使い、
「那覇市 美容室」で正規化後5件以上の関連候補が統合されることをofflineで保証する。

実通信確認は`live_check.bat`で利用者が明示確認した場合だけ行う。この開発コンテナでは外向きCONNECTが
HTTP 403で拒否されたため、実検索5件の確認はWindows実行環境で再実施する。0件時はProvider別エラーと
会社Proxyを確認し、安全上限やrobots方針を緩和しない。
