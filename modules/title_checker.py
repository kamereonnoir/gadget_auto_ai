"""
既存記事タイトルとの重複チェック。
data/articles 内の Markdown から # 1行目を取得し、正規化後に difflib で類似度を判定する。
"""
import os
import re
from difflib import SequenceMatcher

# 類似とみなすしきい値（0.75 より大きい）
SIMILARITY_THRESHOLD = 0.75

# 正規化用: 全角英数字 → 半角
_FULL_TO_HALF = str.maketrans(
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
)


def normalize_title(title: str) -> str:
    """
    比較用にタイトルを正規化する。

    - 小文字化（英字）
    - 全角英数字を半角に
    - 記号を削除
    - 連続スペースを1つに
    - 「おすすめ」「比較」「ランキング」を同一トークンに寄せる
    - 「10選」「5選」などの数字＋選は除去して差を弱める
    """
    if not title:
        return ""
    s = title.strip()
    s = s.translate(_FULL_TO_HALF)
    s = s.lower()
    # 記号削除（英数字・ひらがな・カタカナ・漢字・スペース以外）
    s = re.sub(r"[^\w\s\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    # おすすめ・比較・ランキングを同一扱い
    for word in ("おすすめ", "比較", "ランキング", "お勧め", "おススメ"):
        s = re.sub(re.escape(word), "RECO", s)
    # 数字＋選（5選, 10選など）を除去して差を弱める
    s = re.sub(r"\d+選", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _articles_dir() -> str:
    """data/articles の絶対パス。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "data", "articles")


def _collect_existing_titles() -> list[str]:
    """data/articles 以下の全 .md の先頭 # 行からタイトルを収集。"""
    base = _articles_dir()
    titles: list[str] = []
    if not os.path.isdir(base):
        return titles
    for _root, _dirs, files in os.walk(base):
        for name in files:
            if not name.lower().endswith(".md"):
                continue
            path = os.path.join(_root, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    first = f.readline()
                if first.startswith("#"):
                    t = first.lstrip("#").strip()
                    if t:
                        titles.append(t)
            except OSError:
                continue
    return titles


def is_similar_title(new_title: str) -> bool:
    """
    既存記事に類似タイトルがあるか判定する。

    - 比較前に new_title と既存タイトルを normalize_title してから比較
    - similarity > 0.75 なら類似
    - 片方が片方を含む場合も類似とみなす（正規化後の文字列で判定）
    - 完全一致は類似から除外（自分自身をスキップしない）

    戻り値:
        True  -> 類似あり → 投稿スキップ
        False -> 類似なし → 投稿してよい
    """
    raw_new = (new_title or "").strip()
    if not raw_new:
        return False

    norm_new = normalize_title(raw_new)
    if not norm_new:
        return False

    existing = _collect_existing_titles()
    for existing_title in existing:
        raw_existing = (existing_title or "").strip()
        if not raw_existing:
            continue
        if raw_existing == raw_new:
            continue
        norm_existing = normalize_title(raw_existing)
        if not norm_existing:
            continue
        if norm_new == norm_existing:
            print("[title_checker] 類似タイトルのためスキップ:", new_title)
            print("[title_checker] 既存:", existing_title)
            return True
        ratio = SequenceMatcher(None, norm_new, norm_existing).ratio()
        if ratio > SIMILARITY_THRESHOLD:
            print("[title_checker] 類似タイトルのためスキップ:", new_title)
            print("[title_checker] 既存:", existing_title)
            return True
        # 片方が片方を含む場合も類似とみなす（短すぎる片方は無視）
        if len(norm_new) >= 4 and len(norm_existing) >= 4:
            if norm_new in norm_existing or norm_existing in norm_new:
                print("[title_checker] 類似タイトルのためスキップ:", new_title)
                print("[title_checker] 既存:", existing_title)
                return True
    return False
