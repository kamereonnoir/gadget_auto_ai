from typing import Dict, List, Literal, Optional, Tuple

ArticleType = Literal["compare", "product", "versus", "usecase", "problem"]


def _product_label(product: Dict[str, str]) -> str:
    brand = product.get("brand", "")
    name = product.get("name", "")
    label = f"{brand} {name}".strip()
    return label or "この商品"


def build_internal_links(
    theme: str,
    products: List[Dict[str, str]],
    article_type: ArticleType,
    product_index: Optional[int] = None,
    versus_pair: Optional[Tuple[int, int]] = None,
) -> str:
    """
    記事末尾に付ける「関連記事」セクションを生成する。

    - compare: 商品レビュー記事 + VS 記事への導線
    - product: 比較記事 + 対象商品の VS 記事への導線
    - versus: 比較記事 + 対象2商品の商品レビュー記事への導線
    - usecase: 比較記事 + 商品レビュー + VS 記事への導線（compare と同様）
    - problem: 比較記事 + 商品レビュー + VS 記事への導線（compare と同様）

    現時点ではタイトルベースのテキストのみで、URL までは扱わない。
    """
    lines: List[str] = []
    lines.append("## 関連記事")

    if article_type == "compare" or article_type == "usecase" or article_type == "problem":
        # 商品レビュー記事への導線
        lines.append("")
        lines.append("### 商品レビュー記事")
        for p in products:
            label = _product_label(p)
            lines.append(f"- {label} の個別レビュー記事")

        # VS 記事への導線（先頭3商品の組み合わせを想定）
        if len(products) >= 2:
            lines.append("")
            lines.append("### 商品同士の比較記事")
            n = min(3, len(products))
            for i in range(n):
                for j in range(i + 1, n):
                    label_a = _product_label(products[i])
                    label_b = _product_label(products[j])
                    lines.append(f"- {label_a} vs {label_b} の比較記事")

    elif article_type == "product":
        if product_index is None or not (0 <= product_index < len(products)):
            return "\n".join(lines)

        target = products[product_index]
        target_label = _product_label(target)

        # 比較記事への導線
        lines.append("")
        lines.append("### 比較記事")
        lines.append(f"- {theme}向けおすすめガジェット比較記事")

        # 対象商品の VS 記事への導線
        if len(products) >= 2:
            lines.append("")
            lines.append("### 他モデルとの比較記事")
            n = min(3, len(products))
            for i in range(n):
                if i == product_index:
                    continue
                other_label = _product_label(products[i])
                lines.append(f"- {target_label} vs {other_label} の比較記事")

    elif article_type == "versus":
        if not versus_pair:
            return "\n".join(lines)

        i, j = versus_pair
        if not (0 <= i < len(products) and 0 <= j < len(products)):
            return "\n".join(lines)

        prod_a = products[i]
        prod_b = products[j]
        label_a = _product_label(prod_a)
        label_b = _product_label(prod_b)

        # 比較記事への導線
        lines.append("")
        lines.append("### 比較記事")
        lines.append(f"- {theme}向けおすすめガジェット比較記事")

        # 商品レビュー記事への導線
        lines.append("")
        lines.append("### 商品レビュー記事")
        lines.append(f"- {label_a} の個別レビュー記事")
        lines.append(f"- {label_b} の個別レビュー記事")

    return "\n".join(lines)

