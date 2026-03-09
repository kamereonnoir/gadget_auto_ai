"""
楽天 商品価格ナビ製品検索APIを使って、商品名から楽天の商品情報を取得する。
"""
import os
import re
from typing import Dict
from difflib import SequenceMatcher

import requests
from dotenv import load_dotenv


load_dotenv()

RAKUTEN_PRODUCT_SEARCH_ENDPOINT = "https://app.rakuten.co.jp/services/api/Product/Search/20170426"


def _blank_result() -> Dict[str, str]:
    """失敗時にも固定のキーを空文字で返すヘルパー。"""
    return {
        "product_name": "",
        "brand_name": "",
        "rakuten_url": "",
        "image_url": "",
        "price_text": "",
    }


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def lookup_product(product_name: str, brand: str = "") -> Dict[str, str]:
    """
    楽天 商品価格ナビ製品検索APIを使って商品情報を取得する。

    戻り値は必ず以下のキーを含む dict:
    - product_name
    - brand_name
    - rakuten_url
    - image_url
    - price_text
    """
    app_id = os.getenv("RAKUTEN_APP_ID", "").strip()
    access_key = os.getenv("RAKUTEN_ACCESS_KEY", "").strip()
    affiliate_id = os.getenv("RAKUTEN_AFFILIATE_ID", "").strip()

    # 環境変数が設定されているかだけをログに出す（値は表示しない）
    print(f"[rakuten_lookup] APP_ID set: {bool(app_id)}")
    print(f"[rakuten_lookup] ACCESS_KEY set: {bool(access_key)}")
    print(f"[rakuten_lookup] AFFILIATE_ID set: {bool(affiliate_id)}")

    if not app_id:
        print("[rakuten_lookup] RAKUTEN_APP_ID が未設定のため、楽天検索をスキップします。")
        return _blank_result()

    keyword = (product_name or "").strip()
    if not keyword:
        print("[rakuten_lookup] product_name が空のため、楽天検索をスキップします。")
        return _blank_result()

    params = {
        "applicationId": app_id,
        "keyword": keyword,
        "format": "json",
    }
    if affiliate_id:
        params["affiliateId"] = affiliate_id
    if access_key:
        # 商品価格ナビAPIでは accessId を要求される場合があるため、あれば付与しておく
        params["accessId"] = access_key

    try:
        print(f"[rakuten_lookup] 検索キーワード: {keyword}")
        resp = requests.get(RAKUTEN_PRODUCT_SEARCH_ENDPOINT, params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[rakuten_lookup] 楽天APIリクエスト失敗: {e}")
        return _blank_result()

    try:
        data = resp.json()
    except ValueError as e:
        print(f"[rakuten_lookup] 楽天APIレスポンスのJSON解析に失敗: {e}")
        return _blank_result()

    items = data.get("Products") or data.get("products") or []
    hit_count = len(items)
    print(f"[rakuten_lookup] ヒット件数: {hit_count}")

    if not items:
        return _blank_result()

    target_str = f"{brand} {product_name}".strip() or product_name

    best = None
    best_score = -1.0

    for item in items:
        prod = item.get("Product") or item
        cand_name = prod.get("productName") or prod.get("productNameKana") or ""
        cand_brand = prod.get("brandName") or ""

        cand_str = f"{cand_brand} {cand_name}".strip()
        score = _similarity(target_str, cand_str)

        if score > best_score:
            best_score = score
            best = prod

    if not best:
        return _blank_result()

    cand_name = best.get("productName") or best.get("productNameKana") or ""
    cand_brand = best.get("brandName") or brand or ""

    # rakuten_url の候補を優先順位付きで抽出
    candidates = [
        ("affiliateUrl", best.get("affiliateUrl") or ""),
        ("affiliateUrlPc", best.get("affiliateUrlPc") or ""),
        ("productUrl", best.get("productUrl") or ""),
    ]

    def _looks_like_product_page(url: str) -> bool:
        if not url:
            return False
        u = url.lower()
        # 楽天トップや検索ページなど明らかに汎用ページと思われるものを除外
        if "rakuten.co.jp" not in u:
            return False
        if any(x in u for x in ["/search/", "/spt/top", "/spt/mall"]):
            return False
        # product.rakuten.co.jp を含む、もしくは /item/ /product/ などがあれば商品個別ページとみなす
        if "product.rakuten.co.jp" in u:
            return True
        if any(x in u for x in ["/item/", "/product/"]):
            return True
        # それ以外は一応許可するが優先度は低め（ここでは単純に True にする）
        return True

    rakuten_url = ""
    url_kind = ""
    for kind, url in candidates:
        if not _looks_like_product_page(url):
            continue
        rakuten_url = url
        url_kind = kind
        # affiliateUrl / affiliateUrlPc を使う場合、プレースホルダ「アフィリエイトID」を .env の値で置き換える
        if affiliate_id and kind in ("affiliateUrl", "affiliateUrlPc") and "アフィリエイトID" in rakuten_url:
            rakuten_url = rakuten_url.replace("アフィリエイトID", affiliate_id)
            print(f"[rakuten_lookup] affiliateID適用URL: {rakuten_url}")
        break

    if rakuten_url:
        print(f"[rakuten_lookup] 採用URL種別: {url_kind}")
        print(f"[rakuten_lookup] 採用URL: {rakuten_url}")

    image_url = (
        best.get("mediumImageUrl")
        or best.get("smallImageUrl")
        or best.get("imageUrl")
        or ""
    )

    # 画像URLのサイズ指定をできるだけ大きめに変更（例: _ex=128x128 -> _ex=400x400）
    if image_url and "_ex=" in image_url:
        try:
            image_url = re.sub(r"_ex=\d+x\d+", "_ex=400x400", image_url)
        except re.error:
            pass

    min_price = best.get("minPrice")
    max_price = best.get("maxPrice")
    price_text = ""
    try:
        if min_price and max_price and min_price != max_price:
            price_text = f"価格目安: {min_price}円〜{max_price}円程度"
        elif min_price:
            price_text = f"価格目安: {min_price}円前後"
    except Exception:
        price_text = ""

    print(f"[rakuten_lookup] 採用商品名: {cand_brand} {cand_name}")

    return {
        "product_name": cand_name or product_name,
        "brand_name": cand_brand,
        "rakuten_url": rakuten_url,
        "image_url": image_url,
        "price_text": price_text,
    }

