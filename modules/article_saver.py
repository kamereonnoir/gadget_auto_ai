import os
import re
from typing import Literal


Category = Literal["compare", "product", "versus", "usecase", "problem"]


def _slugify(title: str) -> str:
    """
    タイトル文字列をファイル名用のスラッグに変換する。

    - 全体を小文字化
    - 全角スペースを半角スペースに変換
    - よく使う日本語キーワードを簡易英語に置き換え
    - 英数字とアンダースコア以外はアンダースコアに置換
    - 連続したアンダースコアを 1 つにまとめる
    - 先頭末尾のアンダースコアを削除
    """
    text = title.lower()
    text = text.replace("　", " ")

    # よく使いそうな日本語キーワードを簡易的に英語に置き換え
    replacements = {
        "充電器": "charger",
        "モバイルバッテリー": "mobile_battery",
        "比較": "vs",
        "おすすめ": "top",
        "レビュー": "review",
        "徹底解説": "guide",
        "徹底比較": "vs",
    }
    for jp, en in replacements.items():
        text = text.replace(jp, f" {en} ")

    # 非英数字をアンダースコアに
    text = re.sub(r"[^a-z0-9]+", "_", text)
    # 連続アンダースコアを 1 つに
    text = re.sub(r"_+", "_", text)
    # 先頭末尾のアンダースコアを削除
    text = text.strip("_")

    return text or "article"


def save_article(category: Category, title: str, content: str) -> str:
    """
    記事を data/articles/{category}/ 以下に Markdown 形式で保存する。

    保存形式:
    # タイトル

    本文
    """
    # プロジェクトルート（modules/ の 1 つ上）を基準とする
    root_dir = os.path.dirname(os.path.dirname(__file__))
    articles_dir = os.path.join(root_dir, "data", "articles", category)
    os.makedirs(articles_dir, exist_ok=True)

    slug = _slugify(title)
    filename = f"{slug}.md"
    file_path = os.path.join(articles_dir, filename)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{content}\n")

    rel_path = os.path.relpath(file_path, root_dir)
    print(f"Saved article: {rel_path}")

    return file_path

