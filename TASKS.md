## gadget_auto_ai 開発タスク一覧（TASKS）

このファイルは、`gadget_auto_ai` プロジェクトの開発タスク・未解決の問題・優先順位を人間と AI の両方が追いやすいように整理したものです。

---

### 現在の優先タスク

- **楽天リンクの最終置換確認**
  - `rakuten_product_lookup.py` → `affiliate_builder.py` → `wp_poster.py` までのフローで、楽天アフィリエイトURLに `"アフィリエイトID"` プレースホルダが一切残らないことを再確認する。
  - 実際に記事を生成・投稿し、出力 HTML / WordPress 側の本文をチェックする。

- **Amazonリンク対応**
  - 現在は楽天API中心の購入リンク生成になっている。
  - 今後、Amazon Product Advertising API などを用いて Amazon 側の商品 URL / 画像 / 価格目安も取得し、`affiliate_builder.py` から Amazon ボタンに反映できるようにする。

- **compare 記事の品質改善**
  - `generate_comparison_article()` のプロンプトと後処理を継続的に改善する。
  - タイトルの自然さ・クリックされやすさ（重複除去、不要な年号の削除など）は既に対応済みだが、さらに:
    - 「迷ったらこれ」の説得力
    - 商品ごとのメリット / 注意点の具体性
    - 内部リンク構造（関連記事）の最適化
    を重点的にチューニングする。

- **product / versus 記事の再開準備**
  - いまは compare 記事の安定運用を優先しているため、product / versus 記事の WordPress 投稿が抑制されている箇所がある。
  - compare が安定したら、product / versus 記事についても:
    - 投稿制御フラグ
    - 内部リンク
    - 購入リンク
    の整合性を取りつつ、運用に耐えうる形で再有効化する。

---

### 近日対応したい改善

- **キーワード生成・スコアリングのチューニング**
  - `keyword_generator.py` / `keyword_scorer.py` のプロンプトと閾値を見直し、収益性・検索意図の明確さをより重視したスコアリングロジックにする。

- **ログの整理とレベル分け**
  - 現状は `print` / `logger.info` が混在している箇所があるため、ログレベル（INFO / WARN / ERROR 相当）をある程度揃えておく。
  - 実運用時にノイズとなる DEBUG ログは設定で ON/OFF できるように検討。

- **エラーハンドリングの一貫性向上**
  - OpenAI / 楽天 / WordPress 各 API のエラー時の挙動（フォールバック記事 / スキップ / リトライ有無など）を整理し、サマリーにも明示できるようにする。

---

### 既知の不具合

- **楽天アフィリエイトURLのプレースホルダ確認**
  - 過去の実行で生成済みの `.md` / `.log` に `"アフィリエイトID"` が残っている。
  - 現在は `rakuten_product_lookup.py` → `affiliate_builder.py` → `wp_poster.py` の三段階でプレースホルダ除去のガードを追加済みだが、今後も回帰がないか注意する必要がある。

- **楽天画像が `now_printing` になる商品がある**
  - 楽天APIの `imageUrl` / `mediumImageUrl` に `now_printing` などのプレースホルダ画像が返るケースがある。
  - 記事内の見栄えや CTR に影響するため、将来的に「十分な画像が無い場合のフォールバック表示」（例: 画像非表示 or 汎用アイコン）を検討する。

- **一部商品で楽天検索ヒット率が低い**
  - `lookup_product()` 内で複数パターン（`brand + name`, `brand + name + "充電器"`, `brand + "100W 充電器"`, `name`）を試しているが、それでもヒットしない商品がある。
  - 商品名の正規化ロジックや類似度判定の閾値、カテゴリフィルタなどを調整する余地がある。

---

### 完了済みタスク（このガイド作成時点）

- **Markdown → HTML 変換**
  - `modules/wp_poster.py` で `markdown.markdown()` による本文の HTML 変換を導入。
  - テーブル・リスト・見出し・画像などを含む Markdown を WordPress に適した HTML に変換した上で投稿。

- **画像挿入**
  - `modules/article_generator.py` の `_inject_product_images_markdown()` により、比較記事内の各商品見出し直下に楽天から取得した `image_url` を `<img>` ブロックとして挿入。
  - 画像は中央寄せ・レスポンシブ対応のスタイルに統一。

- **購入リンクカード化**
  - `modules/affiliate_builder.py` で compare 記事用の購入リンクをカード形式の HTML に変更。
  - 商品画像・商品名・短い説明・Amazon / 楽天ボタンを含むカードを縦に並べる構造を実装。

- **GitHub接続**
  - ローカルリポジトリを `git init` → 初期コミット → `origin` として `https://github.com/kamereonnoir/gadget_auto_ai.git` を追加 → `main` ブランチを push 済み。

- **README / DEV_GUIDE 作成**
  - `README.md` にプロジェクト概要・構造・実行方法・必要な環境変数を整理。
  - `DEV_GUIDE.md` に開発フロー・主要モジュールの役割・修正／デバッグルール・今後の優先改善項目を整理。

