"""
キーワードから問題・悩み・疑問リストを生成する。
"""
from typing import List


def generate_problems(keyword: str) -> List[str]:
    """
    キーワードから読者が持ちそうな問題・疑問を3件生成する。
    まずはキーワードを埋め込んだ固定パターンで返す。
    """
    base = (keyword or "").strip() or "ガジェット"
    return [
        f"{base}は必要？",
        f"{base}が熱くなるのは大丈夫？",
        f"{base}の選び方がわからない",
    ]
