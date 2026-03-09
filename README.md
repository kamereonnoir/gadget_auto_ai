## gadget_auto_ai

WordPress にガジェット記事を自動投稿する AI ブログシステムの MVP 用リポジトリです。

現時点では以下だけを実装しています。

- テーマ入力（標準入力 or コマンドライン引数）
- ダミーの商品 5 件の選定（`modules/product_picker.py`）
- シンプルな比較記事本文の生成（`modules/article_generator.py`）
- WordPress 投稿はコンソール出力のみの仮実装（`modules/wp_poster.py`）

### 動作確認方法

```bash
cd gadget_auto_ai
python -m main.py
# もしくは
python -m main.py ワイヤレスイヤホン 比較
```

Windows の場合は以下のように実行してください。

```bash
cd C:\work\python\gadget_auto_ai
python -m main.py
```

### 今後の拡張イメージ

- LLM（例: OpenAI / Azure OpenAI など）を使った高品質な記事生成
- Amazon / 楽天 などからの商品情報自動取得
- WordPress REST API を利用した自動投稿・アイキャッチ画像設定
- 投稿スケジュール管理や、テーマ自動提案など

