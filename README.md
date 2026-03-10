## gadget_auto_ai

ガジェット記事を自動生成して WordPress に投稿する AI ブログシステムです。

OpenAI で記事本文を生成し、楽天APIで商品情報を補完しつつ、WordPress REST API による自動投稿とアフィリエイトリンク生成までを一気通貫で行います。

---

### 主な機能

- **商品検索（楽天API）**
  - `modules/rakuten_product_lookup.py` を通じて、商品名から楽天の商品情報（アフィリエイトURL・画像URL・価格目安など）を取得
- **記事生成（OpenAI）**
  - `modules/article_generator.py` で比較記事・商品レビュー・用途別記事・問題解決記事などを Responses API を使って生成
- **WordPress自動投稿**
  - `modules/wp_poster.py` から WordPress REST API を叩き、カテゴリ・タグ付きで記事を下書き投稿
- **アフィリエイトリンク生成**
  - `modules/affiliate_builder.py` で購入リンクブロックを生成（商品カード形式の HTML・Amazon / 楽天ボタン）

---

### プロジェクト構造

```text
gadget_auto_ai/
  main.py                 # エントリーポイント
  requirements.txt
  README.md

  modules/
    product_picker.py     # テーマごとの商品ピックアップ＆楽天API補完
    article_generator.py  # OpenAI で各種記事を生成
    wp_poster.py          # WordPress REST API 投稿
    affiliate_builder.py  # 購入リンク（アフィリエイト導線）生成
    keyword_generator.py  # テーマから検索キーワード生成
    keyword_scorer.py     # キーワードのスコアリング
    link_builder.py       # 内部リンク（関連記事）生成
    article_saver.py      # Markdown で記事保存
    discord_notifier.py   # Discord Webhook 通知
    title_checker.py      # 類似タイトルチェック
    usecase_generator.py  # 用途別記事のテーマ生成
    problem_generator.py  # 問題解決記事のテーマ生成
    post_queue.py         # 投稿キュー管理
    rakuten_product_lookup.py # 楽天商品検索APIクライアント

  prompts/
    compare_prompt.txt    # 比較記事用のプロンプト（必要に応じて利用）

  data/
    logs/                 # 実行ログ（Git 管理外）
    articles/             # 生成された記事の Markdown（Git 管理外）
    post_queue.json       # 投稿キュー
```

---

### 実行方法

1. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

2. 実行

```bash
python main.py "100W充電器"
```

環境変数や `.env` の設定に応じて、キーワード生成 → 商品ピックアップ → 記事生成 → ファイル保存 → 投稿キュー追加 / WordPress 下書き投稿 まで自動で実行されます。

---

### 必要な環境変数（.env）

少なくとも以下の環境変数を設定してください（`.env` 推奨）。

```env
# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4.1-mini  # など

# Rakuten API
RAKUTEN_APP_ID=your_rakuten_app_id
RAKUTEN_ACCESS_KEY=your_rakuten_access_key
RAKUTEN_AFFILIATE_ID=your_rakuten_affiliate_id

# WordPress
WP_URL=https://your-wordpress-site.com
WP_USER=your_wp_username
WP_APP_PASSWORD=your_wp_app_password
WP_STATUS=draft  # or publish
```

その他、Discord 通知や投稿制御用のフラグなどは `.env.example` を参照してください。

---

### 開発フロー

1. **Issue 作成**  
   バグ報告は `.github/ISSUE_TEMPLATE/bug_report.md`、機能要望は `feature_request.md` のテンプレートを使って作成する。

2. **Cursor で修正**  
   `.cursor/rules.md` に沿って開発。URL は必ず sanitize を通し、WordPress 投稿前に最終チェックを行う。

3. **Commit / Push**  
   小さな修正単位で commit し、`main` に push（またはブランチ作成後に push）。

4. **Pull Request / Review**  
   `.github/pull_request_template.md` に従って PR を作成し、レビューを行う。

5. **GitHub Actions 確認**  
   `.github/workflows/python-check.yml` が push / PR で実行され、Python 構文チェックが通ることを確認してからマージする。

