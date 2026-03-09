## gadget_auto_ai 開発ガイド（DEV_GUIDE）

このドキュメントは、AI アシスタント（Cursor など）や開発者が `gadget_auto_ai` プロジェクトを安全かつ一貫した方針で拡張・修正できるようにするためのガイドです。

---

### プロジェクト概要

`gadget_auto_ai` は、**ガジェット記事を自動生成して WordPress に投稿する AI ブログシステム**です。

- OpenAI Responses API を使って、比較記事・商品レビュー・用途別記事・問題解決記事などを自動生成
- 楽天API（商品価格ナビ製品検索API）で商品情報（アフィリエイトURL・画像URL・価格目安）を補完
- WordPress REST API を通じてカテゴリ・タグ付きで記事を自動投稿（またはキューに積んで段階的に投稿）
- 購入リンク（Amazon / 楽天）を記事末尾にカード形式で自動生成

---

### 主要フロー

1. **キーワード生成**
   - `modules/keyword_generator.py` でテーマから検索キーワード候補を生成（OpenAI）
   - `modules/keyword_scorer.py` でキーワードをスコアリングし、上位のみ採用

2. **商品選定**
   - `modules/product_picker.py` でキーワードに応じた候補商品を選定（100W充電器など）
   - 各商品に対して `modules/rakuten_product_lookup.py` を呼び出し、楽天API経由で `rakuten_url` / `image_url` / `price` を補完

3. **記事生成**
   - `modules/article_generator.py` の各関数で記事を生成
     - `generate_comparison_article(...)` 比較記事（メイン）
     - `generate_product_article(...)` 商品レビュー
     - `generate_versus_article(...)` VS 比較
     - `generate_usecase_article(...)` 用途別記事
     - `generate_problem_article(...)` 問題解決記事
   - 比較記事では、本文中に「## 比較一覧」「## 迷ったらこれ」「## 関連記事」などの構成を持つ Markdown を生成
   - 比較記事の本文には、`_inject_product_images_markdown()` により商品見出し直下に楽天画像 (`image_url`) の `<img>` ブロックを挿入

4. **購入リンク生成**
   - `modules/affiliate_builder.py` で購入リンクブロックを生成
     - compare 記事: 商品カード形式の HTML（画像＋商品名＋短い説明＋Amazon / 楽天ボタン）
     - product / versus 記事: 箇条書き形式（テキストリンク）
   - 楽天URLは `_sanitize_rakuten_url()` を通り、`RAKUTEN_AFFILIATE_ID` が適用されない / プレースホルダが残ることがないようにする

5. **WordPress投稿**
   - `modules/wp_poster.py` の `post_to_wordpress()` で WordPress REST API に POST
   - 本文は Markdown から HTML に変換後（`markdown.markdown`）、さらに `_finalize_rakuten_links()` で楽天URLのプレースホルダを最終チェックしてから投稿
   - 投稿方法は `.env` の `POST_MODE` やキューの設定により、「即時投稿」か「キューに積んだ後、一定数ずつ投稿」を切り替え

---

### 主なモジュールの役割

- **`main.py`**
  - エントリーポイント。全フローのオーケストレーション。
  - 処理の流れ:
    1. テーマ入力 → キーワード生成・スコアリング
    2. 各キーワードについて `product_picker` → `article_generator`
    3. 内部リンク・購入リンクブロックの付与
    4. ローカル保存（`article_saver`）
    5. 投稿キュー追加 / WordPress 直接投稿
    6. Discord 通知と実行サマリー

- **`modules/article_generator.py`**
  - OpenAI Responses API を使った記事生成ロジックを集約。
  - 共通のプロンプトビルダー `_build_prompt` と、比較記事タイトル後処理 `_clean_comparison_title` を持つ。
  - 比較記事本文に画像ブロックを埋め込む `_inject_product_images_markdown`、関連記事見出しを重複しないようにする `_dedupe_related_articles_sections` を持つ。

- **`modules/product_picker.py`**
  - テーマ（例: `"100W充電器"`）に応じて、プリセットの代表商品 5 件を選択。
  - 各商品に対して `lookup_product()`（`rakuten_product_lookup.py`）を呼び出し、`rakuten_url` / `image_url` / `price` を補完。
  - 商品名の正規化（ブランド名重複・不要な接頭辞の除去）もここで行う。

- **`modules/rakuten_product_lookup.py`**
  - 楽天 商品価格ナビ製品検索API クライアント。
  - `lookup_product(product_name, brand)` で:
    - `RAKUTEN_APP_ID`, `RAKUTEN_ACCESS_KEY`, `RAKUTEN_AFFILIATE_ID` を `.env` から読み取る。
    - 検索キーワードに応じて商品候補を取得し、類似度スコアで最適な1件を選択。
    - `affiliateUrl` / `affiliateUrlPc` / `productUrl` から商品ページURL、`imageUrl`、価格目安を返す。

- **`modules/affiliate_builder.py`**
  - 購入リンクブロックの生成を担当。
  - compare 記事では縦並びの HTML カード（画像＋商品名＋説明＋Amazon/楽天ボタン）を生成。
  - `_sanitize_rakuten_url(url)` で `RAKUTEN_AFFILIATE_ID` プレースホルダの置換や、`product.rakuten.co.jp` へのフォールバックを行う。

- **`modules/wp_poster.py`**
  - WordPress REST API 投稿ロジック。
  - `.env` の `WP_URL`, `WP_USER`, `WP_APP_PASSWORD`, `WP_STATUS` を `load_dotenv()` 経由で読み取り。
  - 本文を Markdown→HTML 変換後、`_finalize_rakuten_links(content)` で楽天リンクを最終サニタイズしてから投稿。

---

### 修正時のルール

1. **既存フローを壊さない**
   - `main.py` のフロー（キーワード → 商品 → 記事 → 内部リンク → 購入リンク → 保存 → 投稿）の順序は維持すること。
   - 新しい機能を追加する場合は、既存の挙動（特に compare 記事）に影響しないよう、フラグやオプションで制御する。

2. **compare 記事の挙動を優先確認**
   - このプロジェクトの中心は比較記事（`generate_comparison_article`）。
   - 仕様変更やリファクタリング時は、まず compare 記事の生成〜保存〜投稿〜購入リンク表示までが意図通りかを最優先で確認すること。

3. **投稿前に Markdown → HTML 変換を前提にする**
   - 本文は最終的に `markdown.markdown()` で HTML に変換される。
   - 新しい出力（見出し、リスト、カードHTMLなど）を追加する際は、Markdown→HTML変換後も崩れないかを考慮すること。

4. **楽天リンクは最終的にプレースホルダが残らないこと**
   - `modules/rakuten_product_lookup.py` で `RAKUTEN_AFFILIATE_ID` を適用。
   - `modules/affiliate_builder.py` の `_sanitize_rakuten_url()` でプレースホルダを除去・置換。
   - `modules/wp_poster.py` の `_finalize_rakuten_links()` で投稿直前の最終ガードを行う。
   - いずれかの段階で `"アフィリエイトID"` が残る変更をしないこと。

5. **環境変数は `.env` から読む**
   - API キーや WordPress 接続情報、制御フラグはすべて `.env` 経由で設定する。
   - 追加が必要な場合は `.env.example` にも必ず追記し、README / DEV_GUIDE と矛盾しないようにすること。

---

### デバッグ時のルール

1. **ログを必ず残す**
   - 外部API（OpenAI / 楽天 / WordPress）呼び出し前後には、入力・レスポンス概要・エラー内容を `print` / `logger.info` でロギングする。
   - 実運用で支障のない範囲で、どこまで処理が進んでいるかがログから追える状態を維持すること。

2. **一時的な DEBUG コードは最終的に消す**
   - `raise RuntimeError("DEBUG ...")` や強制的な URL 上書き（例: `rakuten_url = "DEBUG_RAKUTEN_URL"`）などは、デバッグが終わったら必ず削除する。
   - デバッグ用ログは残してもよいが、判別しやすい prefix（`[debug]` / `[affiliate_builder]` など）を付ける。

---

### 今後の優先改善項目

1. **Amazonリンク対応**
   - 現状は楽天APIを中心に補完しているが、Amazon 商品リンク（Amazon Product Advertising API など）にも対応する。
   - `affiliate_builder` で Amazon 側リンクも `.env` や別の補完モジュールから注入できるよう拡張する。

2. **product / versus 再開**
   - 現状は compare 記事を優先的に確認しているため、product / versus 記事の WordPress 投稿や内部リンク導線は一部抑制されている可能性がある。
   - compare の安定運用を前提に、product / versus 記事の投稿・リンク構造を段階的に再有効化する。

3. **自動キーワード拡張**
   - OpenAI によるキーワード生成とスコアリングを活かし、テーマに対するロングテールキーワードを継続的に拡張するロジックを検討する。
   - 既存の `keyword_generator` / `keyword_scorer` をベースに、実際のアクセスデータや SERP からのフィードバックループを設計する。

4. **SEO改善**
   - タイトル・見出し構造・内部リンク構造をさらに最適化する（例: パンくずリスト的な構造、FAQ ブロックなど）。
   - Core Web Vitals やモバイルフレンドリネスを意識しつつ、生成される HTML（特に購入リンクカードや画像ブロック）が軽量かつ読みやすいかを継続的に見直す。

