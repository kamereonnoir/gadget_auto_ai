# gadget_auto_ai 開発ルール

このプロジェクトは **AIブログ自動化システム** です。ガジェット記事を自動生成し、WordPress に投稿します。

---

## 主要モジュールの役割

| モジュール | 役割 |
|-----------|------|
| `main.py` | エントリーポイント。キーワード→商品→記事→内部リンク→購入リンク→保存→投稿のオーケストレーション |
| `product_picker.py` | テーマごとの商品ピックアップ＆楽天API補完 |
| `article_generator.py` | OpenAI で各種記事（比較・商品・VS・用途別・問題解決）を生成 |
| `rakuten_product_lookup.py` | 楽天商品検索APIクライアント |
| `affiliate_builder.py` | 購入リンク（アフィリエイト導線）生成 |
| `wp_poster.py` | WordPress REST API 投稿 |
| `keyword_generator.py` / `keyword_scorer.py` | キーワード生成・スコアリング |
| `link_builder.py` | 内部リンク生成 |
| `article_saver.py` | Markdown で記事保存 |
| `post_queue.py` | 投稿キュー管理 |
| `discord_notifier.py` | Discord Webhook 通知 |

---

## 修正時の原則

1. **既存フローを壊さない**  
   `main.py` の処理順序を維持し、新機能はフラグ・オプションで制御する。

2. **compare 記事の挙動を最優先**  
   比較記事（`generate_comparison_article`）が中心。変更時は compare の生成〜保存〜投稿〜購入リンク表示までを確認する。

3. **URL は必ず sanitize を通す**  
   楽天URL・アフィリエイトURLは `affiliate_builder._sanitize_rakuten_url()` を通し、`wp_poster._finalize_rakuten_links()` で投稿前に最終チェックする。`"アフィリエイトID"` プレースホルダが残らないこと。

4. **WordPress 投稿前に最終チェックを行う**  
   `wp_poster._finalize_rakuten_links()` で楽天URLを最終サニタイズしてから投稿する。

5. **DEBUG コードは最終的に消す**  
   `raise RuntimeError("DEBUG ...")` や強制URL上書きなどはデバッグ後に必ず削除する。デバッグログは `[debug]` などの prefix を付けて判別可能にする。

6. **小さな修正単位で commit する**  
   1つの commit は1つの関心事（バグ修正 or 機能追加 or リファクタ）に絞る。

---

## 環境変数

APIキー・WordPress接続情報は `.env` 経由。追加時は `.env.example` にも追記する。
