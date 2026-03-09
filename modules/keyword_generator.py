import json
import os
from typing import List

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError


load_dotenv()


def _fallback_keywords(theme: str) -> List[str]:
    """
    OpenAI API 失敗時に使う簡易キーワード候補。
    """
    base = theme.strip()
    if not base:
        base = "ガジェット"

    return [
        base,
        f"{base} おすすめ",
        f"{base} 比較",
        f"{base} レビュー",
        f"{base} 人気",
        f"{base} 安い",
        f"{base} 高性能",
        f"{base} 小型",
        f"{base} 失敗しない選び方",
        f"{base} ブログ",
    ]


def _limit_keywords(keywords: List[str], max_n: int | None = None) -> List[str]:
    """
    件数を制限する。max_n が指定されていればそれを使用、未指定時は環境変数 MAX_KEYWORDS を使用。
    """
    if max_n is not None and max_n > 0:
        return keywords[:max_n]
    max_str = os.getenv("MAX_KEYWORDS")
    if max_str:
        try:
            n = int(max_str)
            if n > 0:
                return keywords[:n]
        except ValueError:
            pass
    return keywords[:10]


def generate_keywords(theme: str, max_return: int | None = None) -> List[str]:
    """
    テーマから検索キーワードを生成する。

    - max_return 指定時はその件数まで返す（スコアリング用に多めに取得する場合など）
    - 未指定時は環境変数 MAX_KEYWORDS に従う
    """
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    if not api_key or not model:
        print("[keyword_generator] OPENAI_API_KEY または OPENAI_MODEL が設定されていないため、フォールバックキーワードを返します。")
        return _limit_keywords(_fallback_keywords(theme), max_return)

    client = OpenAI(api_key=api_key)

    prompt = f"""
あなたはSEOに詳しい日本人のガジェットブロガーです。

テーマ: 「{theme}」

このテーマから、検索ユーザーが実際に使いそうな関連キーワードを日本語で 10 個生成してください。

条件:
- 各キーワードは 5〜25 文字程度
- 検索意図がはっきり分かる具体的なキーワードにする
- 重複や意味がほぼ同じものは避ける
- テーマそのものだけでなく、用途・ターゲット・悩み・比較・おすすめ・小型・GaN などもバリエーションに含める

出力形式は必ず次の JSON 形式にしてください:
{{
  "keywords": [
    "キーワード1",
    "キーワード2",
    ...
  ]
}}
"""

    response_text = ""
    try:
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": "あなたはSEOに強い日本語ガジェットブロガーです。必ず JSON 形式で返してください。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            text={"format": {"type": "json_object"}},
        )

        response_text = response.output_text
        data = json.loads(response_text)
        raw_keywords = data.get("keywords", [])

        if not isinstance(raw_keywords, list):
            print("[keyword_generator] keywords が配列ではなかったため、フォールバックキーワードを返します。")
            return _limit_keywords(_fallback_keywords(theme), max_return)

        keywords: List[str] = []
        for k in raw_keywords:
            if isinstance(k, str):
                normalized = k.strip()
                if normalized and normalized not in keywords:
                    keywords.append(normalized)

        if not keywords:
            print("[keyword_generator] 有効なキーワードが生成されなかったため、フォールバックキーワードを返します。")
            return _limit_keywords(_fallback_keywords(theme), max_return)

        return _limit_keywords(keywords, max_return)

    except OpenAIError as e:
        print(f"[keyword_generator] OpenAI API エラー: {e}")
        return _limit_keywords(_fallback_keywords(theme), max_return)
    except json.JSONDecodeError as e:
        print(f"[keyword_generator] JSON デコードエラー: {e}")
        snippet = (response_text or "")[:500]
        print(f"[keyword_generator] 返却テキスト先頭500文字:\n{snippet}")
        return _limit_keywords(_fallback_keywords(theme), max_return)
    except Exception as e:
        print(f"[keyword_generator] 想定外のエラー: {e}")
        return _limit_keywords(_fallback_keywords(theme), max_return)

