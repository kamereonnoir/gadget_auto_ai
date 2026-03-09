"""
記事末尾に追加するアフィリエイト導線ブロック（購入リンク）を生成する。
"""
import os
from typing import Dict, List, Literal, Optional
from urllib.parse import urlparse, parse_qs, unquote

from dotenv import load_dotenv

load_dotenv()

ArticleType = Literal["compare", "product", "versus"]


def _product_label(p: Dict[str, str]) -> str:
    return f"{p.get('brand', '')} {p.get('name', '')}".strip() or "商品"


def _sanitize_rakuten_url(url: str) -> str:
    """
    楽天URLを最終サニタイズする。
    - url が空ならそのまま返す
    - 「アフィリエイトID」を含む場合:
      - .env の RAKUTEN_AFFILIATE_ID があれば置換
      - 無ければ affiliate 系URLは使わず、product.rakuten.co.jp 側のURL(pc パラメータなど)があればそちらを返す
    """
    if not url:
        return url

    affiliate_id = os.getenv("RAKUTEN_AFFILIATE_ID", "").strip()
    print(f"[affiliate_builder] affiliate_id set: {bool(affiliate_id)}")
    print(f"[affiliate_builder] raw rakuten_url={url}")

    if "アフィリエイトID" not in url:
        return url

    if affiliate_id:
        sanitized = url.replace("アフィリエイトID", affiliate_id)
        print(f"[affiliate_builder] sanitized rakuten_url={sanitized}")
        return sanitized

    # affiliateId が無い場合は、商品詳細URLが含まれていればそちらを優先
    print("[affiliate_builder] affiliate id missing")
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        # pc パラメータ（PC向けURL）を優先、なければ m（モバイル）も見る
        for key in ("pc", "m"):
            if key in qs and qs[key]:
                decoded = unquote(qs[key][0])
                if "product.rakuten.co.jp" in decoded:
                    print("[affiliate_builder] rakuten_url sanitized")
                    return decoded
    except Exception:
        pass

    # product.rakuten.co.jp も取れない場合は URL を使わない
    return ""


def _card_for_product(p: Dict[str, str]) -> str:
    """
    比較記事用の1商品分カードHTMLを返す。

    - 画像（image_url があれば表示）
    - 商品名
    - 1行の短い説明（feature）
    - Amazonボタン / 楽天ボタン（URLがある場合のみリンク、それ以外は非リンク文言）
    """
    label = _product_label(p)
    feature = (p.get("feature") or "").strip()
    image_url = (p.get("image_url") or "").strip()

    amazon_url = (p.get("amazon_url") or "").strip()
    if amazon_url:
        amazon_part = (
            f'<a href="{amazon_url}" '
            'style="display:inline-block;padding:6px 12px;margin-right:8px;'
            'background:#ff9900;color:#fff;text-decoration:none;border-radius:4px;'
            'font-size:0.9em;">Amazonで見る</a>'
        )
    else:
        amazon_part = (
            '<span style="font-size:0.85em;color:#666;margin-right:8px;">'
            "Amazonの販売ページを確認"
            "</span>"
        )

    rakuten_url = _sanitize_rakuten_url((p.get("rakuten_url") or "").strip())
    print(f"[affiliate_builder] final rakuten_url={rakuten_url}")
    if rakuten_url:
        rakuten_part = (
            f'<a href="{rakuten_url}" '
            'style="display:inline-block;padding:6px 12px;'
            'background:#bf0000;color:#fff;text-decoration:none;border-radius:4px;'
            'font-size:0.9em;">楽天市場で見る</a>'
        )
    else:
        rakuten_part = (
            '<span style="font-size:0.85em;color:#666;">'
            "楽天市場などの販売ページを確認"
            "</span>"
        )

    img_block = ""
    if image_url:
        img_block = (
            '<div style="flex:0 0 96px;text-align:center;margin-right:12px;">\n'
            f'  <img src="{image_url}" alt="{label}" '
            'style="max-width:96px;width:100%;height:auto;" />\n'
            "</div>\n"
        )

    desc_block = ""
    if feature:
        desc_block = (
            f'<div style="font-size:0.9em;color:#555;margin-bottom:8px;">{feature}</div>\n'
        )

    card_html = (
        '<div style="border:1px solid #ddd;padding:12px;margin:12px 0;'
        'display:flex;align-items:flex-start;">\n'
        f"{img_block}"
        '<div style="flex:1 1 auto;">\n'
        f'  <div style="font-weight:bold;margin-bottom:4px;">{label}</div>\n'
        f"  {desc_block if desc_block else ''}"
        '  <div style="margin-top:4px;">\n'
        f"    {amazon_part}\n"
        f"    {rakuten_part}\n"
        "  </div>\n"
        "</div>\n"
        "</div>"
    )
    return card_html


def _line_for_product(p: Dict[str, str]) -> str:
    """1商品分の「商品名：Amazonで見る / 楽天で見る」行を Markdown で返す。

    - amazon_url / rakuten_url があればそれを使用
    - 未設定時はダミーURLを使わず、「販売ページを確認」のような非リンク文言にする
    """
    label = _product_label(p)

    # Amazon 側
    amazon_url = (p.get("amazon_url") or "").strip()
    if amazon_url:
        amazon_part = f"[Amazonで見る]({amazon_url})"
    else:
        amazon_part = "Amazonの販売ページを確認"

    # 楽天側
    rakuten_url = _sanitize_rakuten_url((p.get("rakuten_url") or "").strip())
    print(f"[affiliate_builder] final rakuten_url={rakuten_url}")
    if rakuten_url:
        rakuten_part = f"[楽天市場で見る]({rakuten_url})"
    else:
        rakuten_part = "楽天市場などの販売ページを確認"

    return f"- **{label}**：{amazon_part} / {rakuten_part}"


def build_affiliate_block(
    products: List[Dict[str, str]],
    article_type: ArticleType,
    target_product: Optional[Dict[str, str]] = None,
    versus_products: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    記事タイプに応じた「購入リンク」セクションの Markdown を返す。

    - compare: products 全体の購入リンク
    - product: target_product のみ
    - versus: versus_products の2商品
    """
    lines = ["## 購入リンク", ""]

    if article_type == "compare":
        # 比較記事ではカード形式のHTMLで購入リンクを表示
        for p in products:
            lines.append(_card_for_product(p))
    elif article_type == "product" and target_product:
        lines.append(_line_for_product(target_product))
    elif article_type == "versus" and versus_products and len(versus_products) >= 2:
        for p in versus_products[:2]:
            lines.append(_line_for_product(p))
    else:
        # フォールバック: 先頭1件
        if products:
            lines.append(_line_for_product(products[0]))

    return "\n".join(lines)
