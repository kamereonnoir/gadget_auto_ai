import re
from typing import List, Dict

from modules.rakuten_product_lookup import lookup_product


def _slug(brand: str, name: str) -> str:
    """brand と name から URL 用スラッグを生成（例: anker-737-charger）。"""
    s = f"{brand} {name}".lower().strip()
    s = re.sub(r"[^\w\s\-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "product"


def _normalize_name(brand: str, name: str) -> str:
    """
    ブランド名と商品名を分離しつつ、同じ単語が2回続く場合は1回にまとめる。

    例:
    - brand="Anker", name="Anker 737 Charger (GaNPrime 120W)" -> "737 Charger (GaNPrime 120W)"
    - brand="CIO",   name="CIO NovaPort DUO 100W"            -> "NovaPort DUO 100W"
    """
    brand = (brand or "").strip()
    name = (name or "").strip()
    if not name:
        return name

    # 先頭のブランド名を除去（大文字小文字は無視）
    if brand:
        pattern = re.compile(rf"^{re.escape(brand)}\s+", re.IGNORECASE)
        name = pattern.sub("", name).strip()

    # 連続する同一単語を1回にまとめる
    tokens = name.split()
    deduped: List[str] = []
    for t in tokens:
        if not deduped or deduped[-1].lower() != t.lower():
            deduped.append(t)
    return " ".join(deduped)


def pick_products(theme: str, count: int = 5) -> List[Dict[str, str]]:
    """
    テーマに応じたダミー商品を返す簡易ロジック。

    - 「100W充電器」「充電器」「USB-C 充電器」など → 100W クラスの充電器
    - 「モバイルバッテリー」「モバブ」など → モバイルバッテリー
    - それ以外 → 汎用ガジェット（ワイヤレスイヤホンなど）
    """
    theme_lower = theme.lower()

    # テーマごとの候補リスト定義
    charger_100w = [
        {
            "name": "737 Charger (GaNPrime 120W)",
            "brand": "Anker",
            "price": "9,980円前後",
            "feature": "最大100W級の高出力に対応したGaN充電器",
            "rakuten_url": "",
        },
        {
            "name": "NovaPort DUO 100W",
            "brand": "CIO",
            "price": "6,000〜7,000円前後",
            "feature": "2ポート同時利用でも高出力を維持しやすいコンパクト充電器",
            "rakuten_url": "",
        },
        {
            "name": "Nexode 100W",
            "brand": "UGREEN",
            "price": "7,000円前後",
            "feature": "4ポート構成でPCとスマホをまとめて充電しやすいモデル",
            "rakuten_url": "",
        },
        {
            "name": "100W Desktop Charger",
            "brand": "Baseus",
            "price": "6,000円前後",
            "feature": "デスクトップ設置向けの多ポート100W充電器",
            "rakuten_url": "",
        },
        {
            "name": "Revo 100W",
            "brand": "Voltme",
            "price": "6,000円前後",
            "feature": "旅行にも持ち運びやすいサイズ感の100Wクラス充電器",
            "rakuten_url": "",
        },
    ]

    mobile_battery = [
        {
            "name": "Anker PowerCore 10000 PD Redux",
            "brand": "Anker",
            "price": "4,000〜5,000円前後",
            "feature": "小型軽量かつPD対応でスマホ充電に最適",
        },
        {
            "name": "CIO SMARTCOBY Pro 30W",
            "brand": "CIO",
            "price": "4,000円前後",
            "feature": "カードサイズ級の小ささで30W出力に対応",
        },
        {
            "name": "UGREEN 10000mAh 20W PD",
            "brand": "UGREEN",
            "price": "3,000〜4,000円前後",
            "feature": "シンプルなデザインでUSB-C高速充電に対応",
        },
        {
            "name": "cheero Power Plus 5",
            "brand": "cheero",
            "price": "3,000円前後",
            "feature": "日本ブランドで安心感のある定番モバイルバッテリー",
        },
        {
            "name": "Anker 622 Magnetic Battery (MagGo)",
            "brand": "Anker",
            "price": "6,000円前後",
            "feature": "MagSafe対応iPhone向けのスタンド一体型モデル",
        },
    ]

    generic_gadgets = [
        {
            "name": "ワイヤレスイヤホン A1",
            "brand": "SoundMax",
            "price": "7,980円",
            "feature": "コスパ重視のエントリーモデル",
        },
        {
            "name": "ワイヤレスイヤホン B2 Pro",
            "brand": "AudioPlus",
            "price": "12,800円",
            "feature": "ノイズキャンセリング搭載",
        },
        {
            "name": "ワイヤレスイヤホン C3 Lite",
            "brand": "PocketSound",
            "price": "4,480円",
            "feature": "軽量＆カラバリ豊富",
        },
        {
            "name": "ワイヤレスイヤホン D4 ANC",
            "brand": "QuietGear",
            "price": "15,980円",
            "feature": "強力なアクティブノイズキャンセリング",
        },
        {
            "name": "ワイヤレスイヤホン E5 Gaming",
            "brand": "GameBeat",
            "price": "9,980円",
            "feature": "低遅延モードでゲーム向き",
        },
    ]

    # テーマ文字列からどのカテゴリを使うかを判定
    if ("100w" in theme_lower) or ("充電器" in theme) or ("charger" in theme_lower):
        base_list = charger_100w
    elif ("モバイルバッテリー" in theme) or ("モバブ" in theme_lower) or ("power bank" in theme_lower):
        base_list = mobile_battery
    else:
        base_list = generic_gadgets

    selected = base_list[:count]

    # 記事生成・アフィリエイト用に各商品に theme を付与し、楽天APIで情報を補完
    for p in selected:
        brand = p.get("brand", "")
        # ブランドと商品名を正規化して重複を避ける
        p["name"] = _normalize_name(brand, p.get("name", ""))
        p["theme"] = theme

        # 楽天APIから rakuten_url / image_url / 価格目安 を補完
        try:
            base_lookup = f"{brand} {p['name']}".strip() or p["name"]
            patterns = [
                base_lookup,
                f"{base_lookup} 充電器".strip(),
                f"{brand} 100W 充電器".strip() if brand else "100W 充電器",
                p["name"],
            ]

            info: Dict[str, str] = {}
            success = False

            for kw in patterns:
                kw = kw.strip()
                if not kw:
                    continue
                print(f"[product_picker] 楽天補完試行: {kw}")
                info = lookup_product(kw, brand=brand)
                if info.get("rakuten_url") or info.get("image_url"):
                    success = True
                    break

            if success:
                print(f"[product_picker] 楽天情報補完成功: {base_lookup}")
            else:
                print(f"[product_picker] 楽天情報補完なし: {base_lookup}")

            if info.get("rakuten_url"):
                p["rakuten_url"] = info["rakuten_url"]
            if info.get("image_url"):
                p["image_url"] = info["image_url"]
            if (not p.get("price")) and info.get("price_text"):
                p["price"] = info["price_text"]

        except Exception as e:
            print(f"[product_picker] 楽天補完中にエラーが発生しました: {e}")

    return selected


