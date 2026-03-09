"""
キーワードを 0〜100 点で評価し、記事化の優先順位付けに使う。
"""
import json
import os
from typing import List, Tuple

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

load_dotenv()


def score_keywords(base_theme: str, keywords: List[str]) -> List[Tuple[str, int, str]]:
    """
    各キーワードを 0〜100 点で評価する。

    評価基準:
    - 検索意図が明確か
    - 商品購入につながりやすいか
    - 比較記事 / 用途記事 / 問題解決記事に展開しやすいか
    - キーワードが広すぎないか
    - 日本語として自然か

    戻り値: [(keyword, score, reason), ...]
    """
    if not keywords:
        return []

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    if not api_key or not model:
        print("[keyword_scorer] OPENAI_API_KEY または OPENAI_MODEL が未設定のため、全キーワードを 50 点で返します。")
        return [(k, 50, "評価スキップ（API 未設定）") for k in keywords]

    keywords_json = json.dumps(keywords, ensure_ascii=False)
    prompt = f"""
あなたはガジェットブログの編集者です。
ベーステーマ「{base_theme}」に対して、以下のキーワードを記事化の優先度で 0〜100 点で評価してください。

評価基準:
- 検索意図が明確か
- 商品購入につながりやすいか
- 比較記事・用途記事・問題解決記事に展開しやすいか
- キーワードが広すぎず具体的か
- 日本語として自然か

キーワード一覧:
{keywords_json}

出力は必ず次の JSON 形式にしてください:
{{
  "scores": [
    {{ "keyword": "キーワード1", "score": 85, "reason": "短い理由" }},
    {{ "keyword": "キーワード2", "score": 72, "reason": "短い理由" }}
  ]
}}

- keyword は上記一覧のいずれかと完全一致させてください。
- score は 0 以上 100 以下の整数にしてください。
- reason は 1 行で簡潔に。
"""

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": "あなたはブログ編集者です。キーワードを数値で評価し、必ず JSON 形式で返してください。",
                },
                {"role": "user", "content": prompt},
            ],
            text={"format": {"type": "json_object"}},
        )
        text = response.output_text
        data = json.loads(text)
        raw = data.get("scores", [])
        if not isinstance(raw, list):
            return _fallback_scored(keywords)

        # キーワード → (score, reason) のマップを作成
        by_keyword: dict[str, Tuple[int, str]] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            k = item.get("keyword") or item.get("key") or ""
            k = k.strip()
            if not k:
                continue
            try:
                s = int(item.get("score", 0))
            except (TypeError, ValueError):
                s = 0
            s = max(0, min(100, s))
            r = (item.get("reason") or "").strip() or "—"
            by_keyword[k] = (s, r)

        result: List[Tuple[str, int, str]] = []
        for k in keywords:
            if k in by_keyword:
                sc, re = by_keyword[k]
                result.append((k, sc, re))
            else:
                # 完全一致しなかった場合は部分一致を探す
                found = None
                for bk, (sc, re) in by_keyword.items():
                    if bk == k or bk.strip() == k:
                        found = (sc, re)
                        break
                if found:
                    result.append((k, found[0], found[1]))
                else:
                    result.append((k, 0, "評価なし"))
        return result
    except (OpenAIError, json.JSONDecodeError, KeyError) as e:
        print(f"[keyword_scorer] 評価エラー: {e}")
        return _fallback_scored(keywords)
    except Exception as e:
        print(f"[keyword_scorer] 想定外のエラー: {e}")
        return _fallback_scored(keywords)


def _fallback_scored(keywords: List[str]) -> List[Tuple[str, int, str]]:
    """API 失敗時は全キーワードを 50 点で返す。"""
    return [(k, 50, "評価スキップ") for k in keywords]
