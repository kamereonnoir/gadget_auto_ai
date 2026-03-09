import os
import sys
import logging
from datetime import datetime

from modules.product_picker import pick_products
from modules.article_generator import (
    generate_comparison_article,
    generate_product_article,
    generate_versus_article,
    generate_usecase_article,
    generate_problem_article,
)
from modules.article_saver import save_article
from modules.keyword_generator import generate_keywords
from modules.keyword_scorer import score_keywords
from modules.usecase_generator import generate_usecases
from modules.problem_generator import generate_problems
from modules.link_builder import build_internal_links
from modules.affiliate_builder import build_affiliate_block
from modules.wp_poster import post_to_wordpress
from modules.post_queue import enqueue_post, dequeue_posts, load_queue
from modules.title_checker import is_similar_title
from modules.discord_notifier import (
    notify_start,
    notify_success,
    notify_error,
    notify_stop,
    notify_summary,
)


def _env_bool(name: str, default: bool) -> bool:
    """環境変数からブール値を読み取るヘルパー。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    """環境変数から整数を読み取るヘルパー。"""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        n = int(raw.strip())
        return n if n >= 0 else default
    except ValueError:
        return default


def _setup_logger() -> logging.Logger:
    """data/logs にファイル出力しつつコンソールにも出すロガーを設定する。"""
    base_dir = os.path.dirname(__file__)
    logs_dir = os.path.join(base_dir, "data", "logs")
    os.makedirs(logs_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(logs_dir, f"run_{ts}.log")

    logger = logging.getLogger("gadget_auto_ai")
    logger.setLevel(logging.INFO)

    # 既存ハンドラをクリア（再実行時の二重出力防止）
    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def main() -> None:
    logger = _setup_logger()
    logger.info("=== gadget_auto_ai start ===")

    # STOP フラグチェック（緊急停止用）
    if os.path.exists("stop.flag"):
        notify_stop("🛑 gadget_auto_ai: STOPフラグ検知。実行を停止します。")
        logger.info("🛑 STOPフラグ検知。実行を停止します。")
        return

    if len(sys.argv) > 1:
        base_theme = " ".join(sys.argv[1:])
    else:
        base_theme = input("ガジェット記事のテーマを入力してください: ").strip()

    if not base_theme:
        logger.info("テーマが空です。処理を終了します。")
        return

    # 開始通知
    notify_start(f"🧠 gadget_auto_ai: 実行開始\nテーマ: {base_theme}")

    # テーマから検索キーワードを生成（スコアリング用に多めに取得）
    keywords_pool = generate_keywords(base_theme, max_return=10)
    # キーワードを評価し、スコア順に並べる
    scored = score_keywords(base_theme, keywords_pool)
    max_keywords = _env_int("MAX_KEYWORDS", 3)
    sorted_scored = sorted(scored, key=lambda x: -x[1])
    keywords = [t[0] for t in sorted_scored][:max_keywords]

    logger.info("=== キーワード評価結果 ===")
    for keyword, score, reason in sorted_scored:
        logger.info("%s | %s | %s", score, keyword, reason)

    # 上位キーワードのみ Discord に通知
    top_lines = [f"{s} | {k}" for k, s, _ in sorted_scored[:max_keywords]]
    notify_success("🧠 gadget_auto_ai: キーワード評価完了\n" + "\n".join(top_lines))

    # 投稿制御フラグ・上限（.env から読み込み）
    enable_compare_post = _env_bool("ENABLE_COMPARE_POST", True)
    enable_product_post = _env_bool("ENABLE_PRODUCT_POST", False)
    enable_versus_post = _env_bool("ENABLE_VERSUS_POST", False)
    max_compare_posts = _env_int("MAX_COMPARE_POSTS", 1)
    max_product_posts = _env_int("MAX_PRODUCT_POSTS", 0)
    max_versus_posts = _env_int("MAX_VERSUS_POSTS", 0)
    post_mode = (os.getenv("POST_MODE") or "queue").strip().lower()
    posts_per_run = _env_int("POSTS_PER_RUN", 1)

    # 実行サマリー用カウンタ
    keywords_count = len(keywords)
    compare_count = 0
    product_count = 0
    versus_count = 0
    compare_posted = 0
    product_posted = 0
    versus_posted = 0
    wp_post_success = 0
    wp_post_failed = 0
    queue_added = 0
    queue_posted = 0

    # 各キーワードごとに記事生成フローを実行
    for keyword in keywords:
        # ループ途中の STOP フラグチェック
        if os.path.exists("stop.flag"):
            notify_stop("🛑 gadget_auto_ai: STOPフラグ検知。処理を停止しました。")
            logger.info("🛑 STOPフラグ検知。処理を停止しました。")
            break

        # compare の投稿上限に達している場合は、それ以降のキーワード処理は行わない
        if compare_posted >= max_compare_posts:
            logger.info("[main] compare記事生成上限に達したため以降のキーワード処理をスキップします。")
            break

        logger.info("==============================")
        logger.info("[main] キーワードで記事生成: %s", keyword)
        logger.info("==============================")

        # キーワードに基づいて商品候補を取得
        products = pick_products(keyword, count=5)

        if enable_compare_post:
            # 比較記事の生成
            compare_title, compare_content = generate_comparison_article(keyword, products)
            compare_count += 1

            # OpenAI 側で「## 関連記事」が既に含まれている場合は、自動関連記事ブロックを追加しない
            if "## 関連記事" in compare_content:
                logger.info("[main] 本文内に関連記事セクションがあるため自動関連記事ブロックをスキップします。")
            else:
                compare_links = build_internal_links(keyword, products, "compare")
                compare_content = f"{compare_content}\n\n{compare_links}"

            # 購入リンクブロックを付与
            compare_affiliate = build_affiliate_block(products, "compare")
            compare_content = f"{compare_content}\n\n{compare_affiliate}"

            logger.info("=== 生成された比較記事タイトル ===")
            logger.info("%s", compare_title)
            logger.info("=== 生成された比較記事本文 ===")
            logger.info("%s", compare_content)

            # 比較記事を保存
            save_article("compare", compare_title, compare_content)

            # 比較記事を WordPress に投稿 or キューに追加（タグ: キーワード + ブランド名）
            compare_brands = sorted({p.get("brand", "") for p in products if p.get("brand")})
            compare_tags = [keyword, *compare_brands]
            logger.info("[main] WordPress投稿: compare")
            if compare_posted >= max_compare_posts:
                logger.info("[main] compare投稿上限に達したためスキップ: %s", compare_title)
                notify_error(
                    "⚠️ gadget_auto_ai skipped\n"
                    "reason: 投稿上限\n"
                    "category: compare\n"
                    f"title: {compare_title}"
                )
            elif is_similar_title(compare_title):
                notify_error(
                    "⚠️ gadget_auto_ai skipped\n"
                    "reason: 類似タイトル\n"
                    f"title: {compare_title}"
                )
            elif post_mode == "queue":
                added = enqueue_post(compare_title, compare_content, "compare", tags=compare_tags)
                if added:
                    queue_added += 1
                    compare_posted += 1
                    logger.info("[main] キューに追加: %s", compare_title)
                    notify_success(f"📥 gadget_auto_ai: キューに追加\ncategory: compare\ntitle: {compare_title}")
                else:
                    logger.info("[main] キュー重複スキップ: %s", compare_title)
            elif post_to_wordpress(compare_title, compare_content, "compare", tags=compare_tags):
                wp_post_success += 1
                compare_posted += 1
                notify_success(f"✅ gadget_auto_ai: 下書き作成\ncategory: compare\ntitle: {compare_title}")
            else:
                wp_post_failed += 1
                notify_error(
                    "⚠️ gadget_auto_ai failed\n"
                    "reason: WordPress投稿失敗\n"
                    f"category: compare\n"
                    f"title: {compare_title}"
                )
        else:
            logger.info("[main] compare記事生成スキップ")

        # 個別商品記事（タイトルのみ表示 & 保存 & WordPress 投稿）
        if enable_product_post:
            logger.info("=== 個別商品記事タイトル一覧 ===")
            for idx, product in enumerate(products):
                product_title, product_content = generate_product_article(keyword, product)
                product_count += 1

                # 商品記事に関連記事セクション・購入リンクを付与
                product_links = build_internal_links(keyword, products, "product", product_index=idx)
                product_content = f"{product_content}\n\n{product_links}"
                product_affiliate = build_affiliate_block(products, "product", target_product=product)
                product_content = f"{product_content}\n\n{product_affiliate}"

                logger.info("- %s", product_title)
                save_article("product", product_title, product_content)

                product_brand = product.get("brand", "")
                product_tags = [keyword]
                if product_brand:
                    product_tags.append(product_brand)
                logger.info("[main] WordPress投稿: product")
                if product_posted >= max_product_posts:
                    logger.info("[main] product投稿上限に達したためスキップ: %s", product_title)
                    notify_error(
                        "⚠️ gadget_auto_ai skipped\n"
                        "reason: 投稿上限\n"
                        "category: product\n"
                        f"title: {product_title}"
                    )
                elif is_similar_title(product_title):
                    notify_error(
                        "⚠️ gadget_auto_ai skipped\n"
                        "reason: 類似タイトル\n"
                        f"title: {product_title}"
                    )
                elif post_mode == "queue":
                    added = enqueue_post(product_title, product_content, "product", tags=product_tags)
                    if added:
                        queue_added += 1
                        product_posted += 1
                        logger.info("[main] キューに追加: %s", product_title)
                        notify_success(f"📥 gadget_auto_ai: キューに追加\ncategory: product\ntitle: {product_title}")
                    else:
                        logger.info("[main] キュー重複スキップ: %s", product_title)
                elif post_to_wordpress(product_title, product_content, "product", tags=product_tags):
                    wp_post_success += 1
                    product_posted += 1
                    notify_success(f"✅ gadget_auto_ai: 下書き作成\ncategory: product\ntitle: {product_title}")
                else:
                    wp_post_failed += 1
                    notify_error(
                        "⚠️ gadget_auto_ai failed\n"
                        "reason: WordPress投稿失敗\n"
                        "category: product\n"
                        f"title: {product_title}"
                    )
        else:
            logger.info("[main] product記事生成スキップ")

        # VS 記事（タイトルのみ表示 & 保存、先頭3商品の組み合わせ）
        if enable_versus_post and len(products) >= 3:
            logger.info("=== VS 記事タイトル一覧 ===")
            index_pairs = [(0, 1), (0, 2), (1, 2)]
            for i, j in index_pairs:
                a = products[i]
                b = products[j]
                vs_title, vs_content = generate_versus_article(keyword, a, b)
                versus_count += 1

                # VS 記事に関連記事セクション・購入リンクを付与
                vs_links = build_internal_links(keyword, products, "versus", versus_pair=(i, j))
                vs_content = f"{vs_content}\n\n{vs_links}"
                vs_affiliate = build_affiliate_block(products, "versus", versus_products=[a, b])
                vs_content = f"{vs_content}\n\n{vs_affiliate}"

                name_a = f"{a.get('brand', '')} {a.get('name', '')}".strip()
                name_b = f"{b.get('brand', '')} {b.get('name', '')}".strip()
                logger.info("- %s  (%s vs %s)", vs_title, name_a, name_b)
                save_article("versus", vs_title, vs_content)

                vs_brands: list[str] = []
                brand_a = a.get("brand", "")
                brand_b = b.get("brand", "")
                if brand_a:
                    vs_brands.append(brand_a)
                if brand_b and brand_b not in vs_brands:
                    vs_brands.append(brand_b)
                vs_tags = [keyword, *vs_brands]
                logger.info("[main] WordPress投稿: versus")
                if versus_posted >= max_versus_posts:
                    logger.info("[main] versus投稿上限に達したためスキップ: %s", vs_title)
                    notify_error(
                        "⚠️ gadget_auto_ai skipped\n"
                        "reason: 投稿上限\n"
                        "category: versus\n"
                        f"title: {vs_title}"
                    )
                elif is_similar_title(vs_title):
                    notify_error(
                        "⚠️ gadget_auto_ai skipped\n"
                        "reason: 類似タイトル\n"
                        f"title: {vs_title}"
                    )
                elif post_mode == "queue":
                    added = enqueue_post(vs_title, vs_content, "versus", tags=vs_tags)
                    if added:
                        queue_added += 1
                        versus_posted += 1
                        logger.info("[main] キューに追加: %s", vs_title)
                        notify_success(f"📥 gadget_auto_ai: キューに追加\ncategory: versus\ntitle: {vs_title}")
                    else:
                        logger.info("[main] キュー重複スキップ: %s", vs_title)
                elif post_to_wordpress(vs_title, vs_content, "versus", tags=vs_tags):
                    wp_post_success += 1
                    versus_posted += 1
                    notify_success(f"✅ gadget_auto_ai: 下書き作成\ncategory: versus\ntitle: {vs_title}")
                else:
                    wp_post_failed += 1
                    notify_error(
                        "⚠️ gadget_auto_ai failed\n"
                        "reason: WordPress投稿失敗\n"
                        "category: versus\n"
                        f"title: {vs_title}"
                    )
        else:
            logger.info("[main] versus記事生成スキップ")

        # 用途記事・問題解決記事は compare 動作確認の間は生成をスキップ
        logger.info("[main] usecase記事生成スキップ")
        logger.info("[main] problem記事生成スキップ")

    # キューモード時: 先頭から POSTS_PER_RUN 件を取り出して投稿（成功したものだけキューから削除）
    if post_mode == "queue" and posts_per_run > 0:
        to_post = dequeue_posts(posts_per_run)
        for item in to_post:
            title = item.get("title", "")
            content = item.get("content", "")
            category = item.get("category", "compare")
            tags = item.get("tags") or []
            if post_to_wordpress(title, content, category, tags=tags):
                queue_posted += 1
                notify_success(f"✅ gadget_auto_ai: キューから投稿完了\ncategory: {category}\ntitle: {title}")
            else:
                added = enqueue_post(title, content, category, tags=tags)
                if not added:
                    logger.info("[main] キュー重複スキップ（既存エントリあり）: %s", title)
                notify_error(
                    "⚠️ gadget_auto_ai: キュー投稿失敗（キューに戻しました）\n"
                    f"category: {category}\ntitle: {title}"
                )

    queue_remaining = len(load_queue())

    # 実行サマリーを表示
    logger.info("==============================")
    logger.info("実行結果")
    logger.info("keywords_count=%s", keywords_count)
    logger.info("compare_count=%s", compare_count)
    logger.info("product_count=%s", product_count)
    logger.info("versus_count=%s", versus_count)
    logger.info("compare_posted=%s", compare_posted)
    logger.info("product_posted=%s", product_posted)
    logger.info("versus_posted=%s", versus_posted)
    logger.info("wp_post_success=%s", wp_post_success)
    logger.info("wp_post_failed=%s", wp_post_failed)
    logger.info("queue_added=%s", queue_added)
    logger.info("queue_posted=%s", queue_posted)
    logger.info("queue_remaining=%s", queue_remaining)
    logger.info("==============================")

    # サマリー通知
    summary_msg = (
        "📊 gadget_auto_ai 実行結果\n"
        f"keywords_count={keywords_count}\n"
        f"compare_count={compare_count}\n"
        f"product_count={product_count}\n"
        f"versus_count={versus_count}\n"
        f"compare_posted={compare_posted}\n"
        f"product_posted={product_posted}\n"
        f"versus_posted={versus_posted}\n"
        f"wp_post_success={wp_post_success}\n"
        f"wp_post_failed={wp_post_failed}\n"
        f"queue_added={queue_added}\n"
        f"queue_posted={queue_posted}\n"
        f"queue_remaining={queue_remaining}\n"
    )
    notify_summary(summary_msg)


if __name__ == "__main__":
    main()

