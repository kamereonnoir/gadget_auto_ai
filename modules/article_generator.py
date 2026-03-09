import json
import os
import re
from typing import List, Dict, Tuple

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError


load_dotenv()


def _build_prompt(theme: str, products: List[Dict[str, str]]) -> str:
    """
    GPT に渡すプロンプトを組み立てる。
    """
    product_lines = []
    for i, p in enumerate(products, start=1):
        product_lines.append(
            f"{i}. ブランド: {p.get('brand')} / 商品名: {p.get('name')} / 価格: {p.get('price')} / 特徴: {p.get('feature')}"
        )
    products_text = "\n".join(product_lines)

    return f"""
あなたは日本のガジェットブロガーです。読者はガジェットに興味はあるが、そこまで詳しくないライトユーザーです。

テーマ: 「{theme}」に関するガジェット比較記事を書いてください。

商品リスト:
{products_text}

出力は JSON 形式で、必ず次の2つのキーを含めてください:
- "title": 記事タイトル（SEO を意識した自然な日本語）
- "content": 記事本文（Markdown形式）

記事本文は Markdown で、次の構成・順番・書き方にしてください（この順番を必ず守ること）:

1. 導入
   - この記事が「どんな人向け」かを最初の1〜2文で明示する
   - 読者がこの記事を読むメリットを簡潔に書く

2. 比較の全体像（比較一覧）
   - 見出し: `## 比較一覧`
   - Markdown のテーブル（|記号を使う）または箇条書きで、各商品の主な違いを一覧できるようにする
   - 価格は「価格の目安」や「おおよその価格帯」という表現にとどめ、最新価格を断定しない

3. 迷ったらこれ（1商品を推薦）
   - 見出し: `## 迷ったらこれ`
   - 特におすすめの1商品を1つだけ挙げる
   - なぜその商品をおすすめするのかを、2〜3個のポイントで簡潔に説明する

4. 各商品の詳細
   - 各商品ごとに `## 商品名` の見出しを付ける
   - その下に本文として、以下のラベルを太字（`**`）で使いながら説明する（小見出しにはしないこと）
     - `**向いている人**`：どんなニーズ・使い方の人に合うか
     - `**メリット**`：主な長所・強み
     - `**注意点**`：事前に知っておくべき弱点や注意事項
   - 箇条書き（`- `）も併用してよいが、`### 向いている人` などの小見出しは使わないこと

5. まとめ
   - 見出し: `## まとめ`
   - 選び方の要点を箇条書きで整理する

6. 関連記事（読み終わった人向けの次の一手）
   - 見出し: `## 関連記事`
   - 同じテーマで読んでおくとよい記事のテーマ例や、どのような切り口の記事を併せて読むと理解が深まるかを、箇条書きで1〜3個程度書く（ここではURLは書かない）

7. 購入リンクへの誘導
   - 記事のいちばん最後に1〜2文だけ追加し、「詳しい仕様や最新価格は、この後に続く購入リンク（Amazonや楽天など）から確認してください」のように自然な形で購入リンクへ誘導する
   - ここでは具体的なURLや `## 購入リンク` の見出しは作らず、あくまでテキストで案内するだけにする（実際の購入リンクセクションはシステム側で追加される前提）

タイトル・表現に関する注意:
- タイトルに西暦の固定年号（「2024年版」など）は入れない
- ブランド名や商品名を二重に繰り返さない（例: 「Anker Anker」「CIO CIO」は避ける）
- 「モバイル比較」など不自然な日本語は避け、文脈に応じて「モバイルバッテリー比較」など自然な表現にする
- 価格は「〜円前後」「〜円程度」「価格の目安は〜」など、あくまで目安として表現する

JSON 以外のテキストは一切出力しないでください。
"""


def _clean_comparison_title(title: str) -> str:
    """
    比較記事タイトルの後処理:
    - 固定年号（2024年版 など）を除去
    - 連続する同一単語（Anker Anker など）を削除
    - いくつかの不自然な表現を自然な形に置き換える
    """
    if not title:
        return title

    cleaned = title

    # 2020〜2099年版 / 年最新 などの固定年号表現を除去
    cleaned = re.sub(r"20[0-9]{2}年(?:版|最新)?", "", cleaned)

    # 連続する同一単語（半角スペース区切り）を1つにまとめる
    parts = cleaned.split()
    deduped: List[str] = []
    for p in parts:
        if not deduped or deduped[-1] != p:
            deduped.append(p)
    cleaned = " ".join(deduped)

    # 不自然な表現の簡易置換
    replacements = {
        "モバイル比較": "モバイルバッテリー比較",
        "比較比較": "比較",
    }
    for bad, good in replacements.items():
        cleaned = cleaned.replace(bad, good)

    # 不要な全角・半角スペースの重複を整理
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    return cleaned


def _inject_product_images_markdown(body: str, products: List[Dict[str, str]]) -> str:
    """
    比較記事の本文Markdownに、各商品の見出し直下に image_url があれば <img> タグを挿入する。
    - image_url がない商品は何も挿入しない
    - 見出し行は '## ' で始まる行を対象とし、見出しテキストに商品名 or ブランド+商品名が含まれる場合に挿入する
    """
    if not body or not products:
        return body

    lines = body.splitlines()
    new_lines: List[str] = []

    for line in lines:
        new_lines.append(line)

        stripped = line.lstrip()
        if stripped.startswith("## "):
            heading_text = stripped[3:].strip()
            heading_lower = heading_text.lower()

            # 見出しに対応する商品を探す
            for p in products:
                brand = (p.get("brand") or "").strip()
                name = (p.get("name") or "").strip()
                image_url = (p.get("image_url") or "").strip()

                if not image_url:
                    continue

                label = f"{brand} {name}".strip()
                candidates = [c.lower() for c in (label, name) if c]

                if candidates and any(c in heading_lower for c in candidates):
                    alt = label or name or "商品画像"
                    img_block = (
                        '<div style="text-align:center; margin: 16px 0;">\n'
                        f'  <img src="{image_url}" alt="{alt}" style="max-width:320px; width:100%; height:auto;">\n'
                        "</div>"
                    )
                    new_lines.append(img_block)
                    break

    return "\n".join(new_lines)


def _dedupe_related_articles_sections(body: str) -> str:
    """
    本文中に複数回現れる「## 関連記事」セクションがある場合、
    最初の1ブロックだけ残し、後ろ側の重複ブロックを削除する。
    """
    if not body:
        return body

    lines = body.splitlines()
    new_lines: List[str] = []
    seen = False
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.lstrip()

        if stripped.startswith("## ") and stripped[3:].strip() == "関連記事":
            if not seen:
                # 最初の「## 関連記事」は残す
                seen = True
                new_lines.append(line)
                i += 1
                # セクション本体を次の「## 」までコピー
                while i < n:
                    nxt = lines[i]
                    if nxt.lstrip().startswith("## ") and nxt.lstrip()[3:].strip() != "関連記事":
                        break
                    # 同じ「## 関連記事」が続く場合はここで止める（重複扱い）
                    if nxt.lstrip().startswith("## ") and nxt.lstrip()[3:].strip() == "関連記事":
                        break
                    new_lines.append(nxt)
                    i += 1
            else:
                # 2つ目以降の「## 関連記事」セクションは、次の「## 」までスキップ
                i += 1
                while i < n:
                    nxt = lines[i]
                    if nxt.lstrip().startswith("## "):
                        break
                    i += 1
        else:
            new_lines.append(line)
            i += 1

    return "\n".join(new_lines)


def _fallback_article(theme: str, products: List[Dict[str, str]]) -> Tuple[str, str]:
    """
    OpenAI API 呼び出しに失敗した場合に使う簡易テンプレ記事。
    """
    title = f"{theme}のおすすめガジェット比較まとめ（簡易版）"

    lines = []
    for i, p in enumerate(products, start=1):
        lines.append(
            f"{i}. {p.get('brand')} {p.get('name')}（{p.get('price')}） - {p.get('feature')}"
        )
    product_section = "\n".join(lines)

    body = f"""## 導入

この記事では、「{theme}」をテーマに、編集部がピックアップしたガジェットを簡単に比較していきます。
まずは候補となる商品をざっと確認してみましょう。

{product_section}

## 比較ポイント

- 価格帯
- 機能・特徴
- サイズや重さ
- どんなシーンに向いているか

## 各商品の特徴

それぞれの商品について、価格や特徴を中心にざっくりと比較してみてください。

## どんな人におすすめか

- コスパ重視でなるべく安く抑えたい人
- 性能重視でしっかり作業やゲームをしたい人
- 持ち運びやすさを優先したい人

自分がどのタイプに当てはまりそうかを意識して選ぶのがおすすめです。

## まとめ

「{theme}」向けのガジェットは、どれを選んでも一長一短があります。
まずはこの記事で挙げた候補の中から、自分の使い方に近いモデルを1〜2個に絞り、
実際のレビューや口コミもチェックしながら最終的な1台を選んでみてください。
"""

    return title, body


def _fallback_product_article(theme: str, product: Dict[str, str]) -> Tuple[str, str]:
    """
    個別商品記事用のフォールバックテンプレ。
    """
    name = product.get("name", "ガジェット")
    brand = product.get("brand", "")
    price = product.get("price", "")

    title = f"{brand} {name} レビュー｜{theme}向けの使い勝手をチェック（簡易版）".strip()

    body = f"""## 導入

この記事では、「{theme}」をテーマに、{brand} {name} の基本的なポイントを簡単にチェックしていきます。

## 商品概要

- 商品名: {brand} {name}
- 想定価格帯: {price}
- 想定用途: {theme}

## 特徴

- 比較的シンプルな構成で扱いやすいモデル
- {theme}用途でも使いやすいバランスの良さ

## メリット

- 初めての人でも選びやすいスタンダードな仕様
- 価格と機能のバランスが取りやすい

## 注意点

- 最新モデルと比べると一部の機能が省かれている可能性があります
- 購入前に公式サイトやレビューで仕様を確認しておくと安心です

## どんな人におすすめか

- はじめて「{theme}」向けのガジェットを試してみたい人
- まずは定番クラスから選びたい人

## まとめ

{brand} {name} は、「{theme}」向けにまずチェックしておきたい候補の1つです。
細かなスペックや最新情報は、公式サイトやレビューもあわせて確認しながら
自分の使い方に合いそうかどうかを判断してみてください。
"""

    return title, body


def generate_comparison_article(theme: str, products: List[Dict[str, str]]) -> Tuple[str, str]:
    """
    OpenAI API を用いて比較記事を生成する。
    失敗した場合はフォールバックのテンプレ記事を返す。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    if not api_key or not model:
        # 設定不足の場合もフォールバック
        print("[article_generator] OPENAI_API_KEY または OPENAI_MODEL が設定されていません。フォールバック記事を返します。")
        return _fallback_article(theme, products)

    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(theme, products)

    try:
        print("[article_generator] OpenAI article generation start...")
        # Responses API を利用して JSON 形式の結果を取得（input 形式）
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": "あなたは日本のガジェットレビューブロガーです。SEO記事を書いてください。必ずJSONで返してください。",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                text={"format": {"type": "json_object"}},
            )
            print("[article_generator] OpenAI article generation done.")
        except Exception as e:
            print(f"[article_generator] OpenAI generation error: {e}")
            raise

        # SDK 1.x 系の高レベルプロパティからテキストを取得
        response_text = response.output_text

        # JSON としてパースし、title と content を取り出す
        data = json.loads(response_text)
        title = _clean_comparison_title(data["title"])
        body = data["content"]

        if not body:
            # 本文が空の場合もフォールバック
            print("[article_generator] 本文が空だったためフォールバック記事を返します。")
            return _fallback_article(theme, products)

        # 各商品の見出し直下に image_url があれば画像タグを差し込む
        body = _inject_product_images_markdown(body, products)

        # 「## 関連記事」が複数ある場合は最初の1ブロックだけ残し重複を削除
        body = _dedupe_related_articles_sections(body)

        return title, body

    except OpenAIError as e:
        print(f"[article_generator] OpenAI API エラー: {e}")
        return _fallback_article(theme, products)
    except json.JSONDecodeError as e:
        print(f"[article_generator] JSON デコードエラー: {e}")
        snippet = (response_text or "")[:500]
        print(f"[article_generator] 返却テキスト先頭500文字:\n{snippet}")
        return _fallback_article(theme, products)
    except Exception as e:
        print(f"[article_generator] 想定外のエラー: {e}")
        return _fallback_article(theme, products)


def generate_product_article(theme: str, product: Dict[str, str]) -> Tuple[str, str]:
    """
    単一商品の個別記事を OpenAI API で生成する。
    失敗時はフォールバックテンプレを返す。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    if not api_key or not model:
        print("[article_generator] OPENAI_API_KEY または OPENAI_MODEL が設定されていません（個別記事）。フォールバック記事を返します。")
        return _fallback_product_article(theme, product)

    client = OpenAI(api_key=api_key)

    name = product.get("name", "ガジェット")
    brand = product.get("brand", "")
    price = product.get("price", "")
    feature = product.get("feature", "")

    prompt = f"""
あなたは日本のガジェットレビューブロガーです。
以下の情報をもとに、商品ごとのレビュー記事を書いてください。

テーマ: {theme}
商品名: {brand} {name}
価格: {price}
特徴: {feature}

記事は日本語で、次の構成を必ず含めてください:
- 導入
- 商品概要
- 特徴
- メリット
- 注意点
- どんな人におすすめか
- まとめ

出力は必ず JSON 形式で、以下の2つのキーを含めてください:
{{
  "title": "SEO を意識した自然な日本語のタイトル",
  "content": "上記構成を満たす本文（Markdown 形式可）"
}}
"""

    try:
        print("[article_generator] OpenAI article generation start...")
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": "あなたは日本のガジェットレビューブロガーです。SEO を意識した商品レビュー記事を書いてください。必ず JSON で返してください。",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                text={"format": {"type": "json_object"}},
            )
            print("[article_generator] OpenAI article generation done.")
        except Exception as e:
            print(f"[article_generator] OpenAI generation error: {e}")
            raise

        response_text = response.output_text
        data = json.loads(response_text)
        title = data["title"]
        body = data["content"]

        if not body:
            print("[article_generator] 個別記事: 本文が空だったためフォールバック記事を返します。")
            return _fallback_product_article(theme, product)

        return title, body

    except OpenAIError as e:
        print(f"[article_generator] 個別記事: OpenAI API エラー: {e}")
        return _fallback_product_article(theme, product)
    except json.JSONDecodeError as e:
        print(f"[article_generator] 個別記事: JSON デコードエラー: {e}")
        snippet = (response_text or "")[:500]
        print(f"[article_generator] 個別記事: 返却テキスト先頭500文字:\n{snippet}")
        return _fallback_product_article(theme, product)
    except Exception as e:
        print(f"[article_generator] 個別記事: 想定外のエラー: {e}")
        return _fallback_product_article(theme, product)


def _fallback_versus_article(
    theme: str, product_a: Dict[str, str], product_b: Dict[str, str]
) -> Tuple[str, str]:
    """
    2商品比較（VS）記事用のフォールバックテンプレ。
    """
    name_a = f"{product_a.get('brand', '')} {product_a.get('name', '')}".strip()
    name_b = f"{product_b.get('brand', '')} {product_b.get('name', '')}".strip()

    title = f"{name_a} vs {name_b} 徹底比較｜{theme}向けにはどっちが最適？"

    body = f"""## 導入

この記事では、「{theme}」をテーマに、{name_a} と {name_b} の2つを簡単に比較していきます。

## 2商品の違い

- デザインやサイズ感、価格帯など、基本的な方向性の違いをチェックします。
- 実際の使い方をイメージしながら、自分に合いそうなほうを絞り込んでいきましょう。

## スペック・特徴の比較

- {name_a}: スペックや特徴はメーカー公式サイトや販売ページを参考にしてください。
- {name_b}: 同様に、詳細な仕様は公式情報もあわせて確認するのがおすすめです。

## それぞれ向いている人

- {name_a} が向いている人:
  - {theme}用途で、できるだけ安心感のある定番モデルを選びたい人
  - シンプルで分かりやすい構成を重視する人

- {name_b} が向いている人:
  - 少し攻めた機能やデザインを試してみたい人
  - コスパや独自機能に魅力を感じる人

## まとめ

「{theme}」向けのガジェットとしては、{name_a} も {name_b} もそれぞれ一長一短があります。
最終的には、自分の使い方や予算、好みのデザインなどを踏まえてどちらがしっくり来るかで選ぶのがおすすめです。
気になる方は、実際のレビューや口コミもあわせてチェックしてみてください。
"""

    return title, body


def generate_versus_article(
    theme: str, product_a: Dict[str, str], product_b: Dict[str, str]
) -> Tuple[str, str]:
    """
    2 商品の VS 比較記事を OpenAI API で生成する。
    失敗時はフォールバックテンプレを返す。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    if not api_key or not model:
        print("[article_generator] OPENAI_API_KEY または OPENAI_MODEL が設定されていません（VS記事）。フォールバック記事を返します。")
        return _fallback_versus_article(theme, product_a, product_b)

    client = OpenAI(api_key=api_key)

    name_a = product_a.get("name", "ガジェットA")
    brand_a = product_a.get("brand", "")
    price_a = product_a.get("price", "")
    feature_a = product_a.get("feature", "")

    name_b = product_b.get("name", "ガジェットB")
    brand_b = product_b.get("brand", "")
    price_b = product_b.get("price", "")
    feature_b = product_b.get("feature", "")

    prompt = f"""
あなたは日本のガジェットレビューブロガーです。
以下の2商品を「{theme}」という切り口で比較する VS 記事を書いてください。

[商品A]
- 商品名: {brand_a} {name_a}
- 価格: {price_a}
- 特徴: {feature_a}

[商品B]
- 商品名: {brand_b} {name_b}
- 価格: {price_b}
- 特徴: {feature_b}

記事は日本語で、次の構成を必ず含めてください:
- 導入
- 2商品の違い
- スペック・特徴の比較
- それぞれ向いている人
- まとめ

出力は必ず JSON 形式で、以下の2つのキーを含めてください:
{{
  "title": "SEO を意識した自然な日本語のタイトル（例: '{brand_a} {name_a} vs {brand_b} {name_b} 徹底比較｜{theme}向けにはどっち？' など）",
  "content": "上記構成を満たす本文（Markdown 形式可）"
}}
"""

    try:
        print("[article_generator] OpenAI article generation start...")
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": "あなたは日本のガジェットレビューブロガーです。SEO を意識した 2 商品の比較記事を書いてください。必ず JSON で返してください。",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                text={"format": {"type": "json_object"}},
            )
            print("[article_generator] OpenAI article generation done.")
        except Exception as e:
            print(f"[article_generator] OpenAI generation error: {e}")
            raise

        response_text = response.output_text
        data = json.loads(response_text)
        title = data["title"]
        body = data["content"]

        if not body:
            print("[article_generator] VS記事: 本文が空だったためフォールバック記事を返します。")
            return _fallback_versus_article(theme, product_a, product_b)

        return title, body

    except OpenAIError as e:
        print(f"[article_generator] VS記事: OpenAI API エラー: {e}")
        return _fallback_versus_article(theme, product_a, product_b)
    except json.JSONDecodeError as e:
        print(f"[article_generator] VS記事: JSON デコードエラー: {e}")
        snippet = (response_text or "")[:500]
        print(f"[article_generator] VS記事: 返却テキスト先頭500文字:\n{snippet}")
        return _fallback_versus_article(theme, product_a, product_b)
    except Exception as e:
        print(f"[article_generator] VS記事: 想定外のエラー: {e}")
        return _fallback_versus_article(theme, product_a, product_b)


def _fallback_usecase_article(
    keyword: str, usecase: str, products: List[Dict[str, str]]
) -> Tuple[str, str]:
    """用途記事用のフォールバックテンプレ。"""
    title = f"{keyword}｜{usecase}向けおすすめガジェット（簡易版）"
    product_lines = "\n".join(
        f"- {p.get('brand', '')} {p.get('name', '')}（{p.get('price', '')}）"
        for p in products
    )
    body = f"""## 導入

この記事では、「{keyword}」のなかでも特に「{usecase}」という用途・シーンに合うガジェットをピックアップしています。

## この用途で重視したいポイント

- 用途「{usecase}」に合わせた選び方のポイントをチェックしましょう。
- 価格・サイズ・機能のバランスも用途に応じて変わります。

## おすすめ商品

{product_lines}

## 商品ごとの向いている人

各商品の特徴に合わせて、自分に合いそうなものを絞り込んでみてください。

## 注意点

- 最新の価格・在庫は販売ページでご確認ください。
- 用途に合うかは個人差があります。

## まとめ

「{usecase}」向けには、上記の商品を比較しながら選ぶのがおすすめです。
"""
    return title, body


def generate_usecase_article(
    keyword: str, usecase: str, products: List[Dict[str, str]]
) -> Tuple[str, str]:
    """
    用途別記事を OpenAI API で生成する。
    失敗時はフォールバックテンプレを返す。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    if not api_key or not model:
        print("[article_generator] OPENAI_API_KEY または OPENAI_MODEL が設定されていません（用途記事）。フォールバック記事を返します。")
        return _fallback_usecase_article(keyword, usecase, products)

    client = OpenAI(api_key=api_key)
    product_text = "\n".join(
        f"- {p.get('brand', '')} {p.get('name', '')} / 価格: {p.get('price', '')} / 特徴: {p.get('feature', '')}"
        for p in products
    )

    prompt = f"""
あなたは日本のガジェットレビューブロガーです。
「{keyword}」に関連するガジェットのうち、「{usecase}」という用途・シーン向けの記事を書いてください。

商品リスト:
{product_text}

記事は日本語で、次の構成を必ず含めてください:
- 導入
- この用途で重視したいポイント
- おすすめ商品
- 商品ごとの向いている人
- 注意点
- まとめ

出力は必ず JSON 形式で、以下の2つのキーを含めてください:
{{
  "title": "SEO を意識した自然な日本語のタイトル（例: 「{keyword}｜{usecase}向けおすすめ」など）",
  "content": "上記構成を満たす本文（Markdown 形式可）"
}}
"""

    response_text = ""
    try:
        print("[article_generator] OpenAI article generation start...")
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": "あなたは日本のガジェットレビューブロガーです。用途別のガイド記事を書いてください。必ず JSON で返してください。",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                text={"format": {"type": "json_object"}},
            )
            print("[article_generator] OpenAI article generation done.")
        except Exception as e:
            print(f"[article_generator] OpenAI generation error: {e}")
            raise

        response_text = response.output_text
        data = json.loads(response_text)
        title = data["title"]
        body = data["content"]
        if not body:
            return _fallback_usecase_article(keyword, usecase, products)
        return title, body
    except OpenAIError as e:
        print(f"[article_generator] 用途記事: OpenAI API エラー: {e}")
        return _fallback_usecase_article(keyword, usecase, products)
    except json.JSONDecodeError as e:
        print(f"[article_generator] 用途記事: JSON デコードエラー: {e}")
        snippet = (response_text or "")[:500]
        print(f"[article_generator] 用途記事: 返却テキスト先頭500文字:\n{snippet}")
        return _fallback_usecase_article(keyword, usecase, products)
    except Exception as e:
        print(f"[article_generator] 用途記事: 想定外のエラー: {e}")
        return _fallback_usecase_article(keyword, usecase, products)


def _fallback_problem_article(
    keyword: str, problem: str, products: List[Dict[str, str]]
) -> Tuple[str, str]:
    """問題解決記事用のフォールバックテンプレ。"""
    title = f"{keyword}｜{problem} を解説（簡易版）"
    product_lines = "\n".join(
        f"- {p.get('brand', '')} {p.get('name', '')}（{p.get('price', '')}）"
        for p in products
    )
    body = f"""## 導入

「{problem}」という疑問や悩みに答えるため、{keyword} の観点から整理します。

## この問題が起きる理由

- よくある原因や背景を押さえておくと、解決策を選びやすくなります。

## 解決のポイント

- 選び方や使い方のポイントをチェックしましょう。

## おすすめ商品

{product_lines}

## 注意点

- 最新の仕様・価格は販売ページでご確認ください。

## まとめ

「{problem}」については、上記を参考に自分に合う商品を選んでみてください。
"""
    return title, body


def generate_problem_article(
    keyword: str, problem: str, products: List[Dict[str, str]]
) -> Tuple[str, str]:
    """
    問題解決記事を OpenAI API で生成する。
    失敗時はフォールバックテンプレを返す。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

    if not api_key or not model:
        print("[article_generator] OPENAI_API_KEY または OPENAI_MODEL が設定されていません（問題解決記事）。フォールバック記事を返します。")
        return _fallback_problem_article(keyword, problem, products)

    client = OpenAI(api_key=api_key)
    product_text = "\n".join(
        f"- {p.get('brand', '')} {p.get('name', '')} / 価格: {p.get('price', '')} / 特徴: {p.get('feature', '')}"
        for p in products
    )

    prompt = f"""
あなたは日本のガジェットレビューブロガーです。
「{keyword}」に関連して、読者の悩み・疑問「{problem}」に答える問題解決記事を書いてください。

商品リスト（解決の参考として紹介してよい）:
{product_text}

記事は日本語で、次の構成を必ず含めてください:
- 導入
- この問題が起きる理由
- 解決のポイント
- おすすめ商品
- 注意点
- まとめ

出力は必ず JSON 形式で、以下の2つのキーを含めてください:
{{
  "title": "SEO を意識した自然な日本語のタイトル（疑問形や「〜で解決」など）",
  "content": "上記構成を満たす本文（Markdown 形式可）"
}}
"""

    response_text = ""
    try:
        print("[article_generator] OpenAI article generation start...")
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {
                        "role": "system",
                        "content": "あなたは日本のガジェットレビューブロガーです。読者の悩み・疑問に答える問題解決記事を書いてください。必ず JSON で返してください。",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                text={"format": {"type": "json_object"}},
            )
            print("[article_generator] OpenAI article generation done.")
        except Exception as e:
            print(f"[article_generator] OpenAI generation error: {e}")
            raise

        response_text = response.output_text
        data = json.loads(response_text)
        title = data["title"]
        body = data["content"]
        if not body:
            return _fallback_problem_article(keyword, problem, products)
        return title, body
    except OpenAIError as e:
        print(f"[article_generator] 問題解決記事: OpenAI API エラー: {e}")
        return _fallback_problem_article(keyword, problem, products)
    except json.JSONDecodeError as e:
        print(f"[article_generator] 問題解決記事: JSON デコードエラー: {e}")
        snippet = (response_text or "")[:500]
        print(f"[article_generator] 問題解決記事: 返却テキスト先頭500文字:\n{snippet}")
        return _fallback_problem_article(keyword, problem, products)
    except Exception as e:
        print(f"[article_generator] 問題解決記事: 想定外のエラー: {e}")
        return _fallback_problem_article(keyword, problem, products)

