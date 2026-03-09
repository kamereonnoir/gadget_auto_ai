"""
WordPress 投稿キュー。記事をキューに積み、後から順番に投稿する。
"""
import json
import os
from typing import Any, Dict, List

# キュー保存先（プロジェクトルート基準の相対パス）
QUEUE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "post_queue.json")


def _ensure_data_dir() -> None:
    """data ディレクトリが存在するようにする。"""
    dir_path = os.path.dirname(QUEUE_PATH)
    if dir_path and not os.path.isdir(dir_path):
        os.makedirs(dir_path, exist_ok=True)


def load_queue() -> List[Dict[str, Any]]:
    """キューを data/post_queue.json から読み込む。"""
    if not os.path.isfile(QUEUE_PATH):
        return []
    try:
        with open(QUEUE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except (json.JSONDecodeError, OSError):
        return []


def save_queue(queue: List[Dict[str, Any]]) -> None:
    """キューを data/post_queue.json に保存する。"""
    _ensure_data_dir()
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def _normalize_title(title: str) -> str:
    """タイトルを前後空白除去 + 小文字化して比較用に正規化する。"""
    return (title or "").strip().lower()


def is_duplicated_title(title: str, queue: List[Dict[str, Any]] | None = None) -> bool:
    """
    キュー内に同じタイトル（前後空白除去 + 小文字化）が存在するか判定する。
    """
    if queue is None:
        queue = load_queue()
    target = _normalize_title(title)
    if not target:
        return False
    for item in queue:
        if _normalize_title(item.get("title", "")) == target:
            return True
    return False


def enqueue_post(
    title: str,
    content: str,
    category: str,
    tags: List[str] | None = None,
) -> bool:
    """
    1件の投稿をキューに追加する。

    すでに同じタイトルが存在する場合は追加せず False を返す。
    追加できた場合のみ保存し True を返す。
    """
    item = {
        "title": title,
        "content": content,
        "category": category,
        "tags": tags if tags is not None else [],
    }
    q = load_queue()
    if is_duplicated_title(title, q):
        return False
    q.append(item)
    save_queue(q)
    return True


def dequeue_posts(limit: int) -> List[Dict[str, Any]]:
    """
    キュー先頭から limit 件を取り出して返す。
    取り出した分はキューから削除され、残りは保存される。
    """
    if limit <= 0:
        return []
    q = load_queue()
    taken = q[:limit]
    remaining = q[limit:]
    save_queue(remaining)
    return taken
