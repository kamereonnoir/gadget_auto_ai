import os
from typing import Literal, Optional, List

import requests
from dotenv import load_dotenv
import markdown


Category = Literal["compare", "product", "versus"]

load_dotenv()


def _get_wp_config() -> Optional[dict]:
    """
    .env から WordPress 接続情報を取得する。
    不足がある場合は None を返す。
    """
    url = os.getenv("WP_URL", "").rstrip("/")
    # 万一 WP_URL に /wp-json/wp/v2 まで含まれている場合はベースURLに正規化する
    suffix = "/wp-json/wp/v2"
    if url.endswith(suffix):
        url = url[: -len(suffix)]
    user = os.getenv("WP_USER", "")
    app_password = os.getenv("WP_APP_PASSWORD", "")
    status = os.getenv("WP_STATUS", "draft")

    if not url or not user or not app_password:
        print("[wp_poster] WP_URL / WP_USER / WP_APP_PASSWORD のいずれかが未設定のため、投稿をスキップします。")
        return None

    return {
        "url": url,
        "user": user,
        "app_password": app_password,
        "status": status,
    }


def _finalize_rakuten_links(content: str) -> str:
    """
    本文中に残っている楽天アフィリエイトURLの「アフィリエイトID」プレースホルダを最終的に除去する。
    """
    if not content:
        return content
    if "アフィリエイトID" not in content:
        return content

    affiliate_id = os.getenv("RAKUTEN_AFFILIATE_ID", "").strip()

    # affiliate ID がある場合は、プレースホルダを置き換えるだけで済ませる
    if affiliate_id:
        updated = content.replace("アフィリエイトID", affiliate_id)
        print("[wp_poster] rakuten link finalized")
        return updated

    # affiliate ID が無い場合は、pc= または m= パラメータから product.rakuten.co.jp のURLを取り出して差し替える
    print("[wp_poster] affiliate id missing, fallback to productUrl")
    import re
    from urllib.parse import unquote

    def _replace_match(match: re.Match) -> str:
        url = match.group(0)
        # クエリの pc= または m= の値を抽出
        m = re.search(r"[?&](pc|m)=([^&]+)", url)
        if not m:
            return url
        decoded = unquote(m.group(2))
        if "product.rakuten.co.jp" in decoded:
            print("[wp_poster] rakuten link finalized")
            return decoded
        return url

    pattern = re.compile(r"https://hb\.afl\.rakuten\.co\.jp/hgc/アフィリエイトID/[^\s\"']+")
    return pattern.sub(_replace_match, content)


def _get_or_create_term(
    term_type: Literal["categories", "tags"],
    name: str,
    config: dict,
) -> Optional[int]:
    """
    指定した名前のカテゴリ / タグの ID を取得する。
    存在しない場合は作成を試みる。
    """
    base = f"{config['url']}/wp-json/wp/v2/{term_type}"
    print(f"[wp_poster] {term_type}_url={base}")

    try:
        res = requests.get(
            base,
            params={"search": name},
            auth=(config["user"], config["app_password"]),
            timeout=10,
        )
        if res.status_code == 200:
            items = res.json()
            for item in items:
                if item.get("name") == name:
                    return item.get("id")
    except requests.RequestException as e:
        print(f"[wp_poster] {term_type} の取得に失敗しました: {e}")
        return None

    # なければ作成
    try:
        create_res = requests.post(
            base,
            json={"name": name},
            auth=(config["user"], config["app_password"]),
            timeout=10,
        )
        if create_res.status_code >= 400:
            print(f"[wp_poster] {term_type} の作成に失敗しました: status={create_res.status_code}")
            try:
                print(f"[wp_poster] レスポンス内容: {create_res.text[:500]}")
            except Exception:
                pass
            return None

        created = create_res.json()
        return created.get("id")
    except requests.RequestException as e:
        print(f"[wp_poster] {term_type} の作成リクエストに失敗しました: {e}")
        return None


def _resolve_category_ids(category: Category, config: dict) -> List[int]:
    """
    compare / product / versus に応じて、対応する WordPress カテゴリを紐づける。
    - compare -> 「比較記事」
    - product -> 「商品レビュー」
    - versus  -> 「商品比較」
    """
    name_map = {
        "compare": "比較記事",
        "product": "商品レビュー",
        "versus": "商品比較",
    }
    name = name_map.get(category)
    if not name:
        return []

    term_id = _get_or_create_term("categories", name, config)
    return [term_id] if term_id is not None else []


def _resolve_tag_ids(tag_names: List[str], config: dict) -> List[int]:
    """
    タグ名のリストから、対応するタグ ID のリストを取得（必要に応じて作成）
    """
    ids: List[int] = []
    seen: set[int] = set()
    for name in tag_names:
        if not name:
            continue
        term_id = _get_or_create_term("tags", name, config)
        if term_id is not None and term_id not in seen:
            seen.add(term_id)
            ids.append(term_id)
    return ids


def post_to_wordpress(
    title: str,
    content: str,
    category: Category,
    tags: Optional[List[str]] = None,
) -> bool:
    """WordPress の REST API を使って記事を投稿する。

    戻り値:
        True  -> 投稿成功
        False -> 投稿失敗またはスキップ
    """
    config = _get_wp_config()
    if config is None:
        return False

    posts_url = f"{config['url']}/wp-json/wp/v2/posts"
    print(f"[wp_poster] posts_url={posts_url}")

    # Markdown を HTML に変換してから送信する
    try:
        html_content = markdown.markdown(
            content,
            extensions=["extra", "sane_lists", "tables"],
        )
    except Exception as e:
        print(f"[wp_poster] Markdown -> HTML 変換に失敗しました: {e}")
        html_content = content

    preview = (html_content or "")[:200]
    print(f"[wp_poster] HTML preview: {preview!r}")

    # 最終的に楽天アフィリエイトURLのプレースホルダを除去
    html_content = _finalize_rakuten_links(html_content)

    data: dict = {
        "title": title,
        "content": html_content,
        "status": config["status"],
    }

    # カテゴリ ID を付与
    cat_ids = _resolve_category_ids(category, config)
    if cat_ids:
        data["categories"] = cat_ids

    # タグ ID を付与
    if tags:
        tag_ids = _resolve_tag_ids(tags, config)
        if tag_ids:
            data["tags"] = tag_ids

    try:
        response = requests.post(
            posts_url,
            json=data,
            auth=(config["user"], config["app_password"]),
            timeout=15,
        )
    except requests.RequestException as e:
        print(f"[wp_poster] WordPress への接続に失敗しました: {e}")
        return False

    if response.status_code >= 400:
        print(f"[wp_poster] 投稿に失敗しました: status={response.status_code}")
        try:
            print(f"[wp_poster] レスポンス内容: {response.text[:500]}")
        except Exception:
            pass
        return False

    try:
        body = response.json()
    except ValueError:
        print("[wp_poster] 投稿は成功した可能性がありますが、レスポンスの JSON 解析に失敗しました。")
        print(f"[wp_poster] レスポンス生データ: {response.text[:500]}")
        return False

    post_id = body.get("id")
    link = body.get("link")

    if link:
        print(f"[wp_poster] 投稿成功 ({category}): {link}")
        return True
    if post_id is not None:
        print(f"[wp_poster] 投稿成功 ({category}): post_id={post_id}")
        return True

    print("[wp_poster] 投稿は成功しましたが、ID/URL を取得できませんでした。")
    return False

