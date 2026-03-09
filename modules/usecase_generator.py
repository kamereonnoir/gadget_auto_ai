"""
キーワードから用途（ユースケース）リストを生成する。
"""
from typing import List


# まずは固定で3件の用途を返す簡易ロジック
DEFAULT_USECASES = [
    "MacBook向け",
    "出張向け",
    "コスパ重視",
]


def generate_usecases(keyword: str) -> List[str]:
    """
    キーワードから用途を3件生成する。
    現状は固定リストを返す。のちに OpenAI やキーワードに応じたロジックに差し替え可能。
    """
    return list(DEFAULT_USECASES)
