import os
from typing import Optional

import requests
from dotenv import load_dotenv


load_dotenv()


def _get_webhook_url() -> Optional[str]:
    url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        print("[discord_notifier] DISCORD_WEBHOOK_URL が未設定のため、通知をスキップします。")
        return None
    return url


def send_discord_message(message: str) -> None:
    """
    Discord Webhook にシンプルなテキストメッセージを送信する。
    エラー時はログ出力のみで、処理は継続する。
    """
    url = _get_webhook_url()
    if not url:
        return

    payload = {"content": message}

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code >= 400:
            print(f"[discord_notifier] 通知に失敗しました: status={response.status_code}")
            try:
                print(f"[discord_notifier] レスポンス内容: {response.text[:500]}")
            except Exception:
                pass
    except requests.RequestException as e:
        print(f"[discord_notifier] 通知送信中にエラーが発生しました: {e}")


def notify_start(message: str) -> None:
    send_discord_message(message)


def notify_success(message: str) -> None:
    send_discord_message(message)


def notify_error(message: str) -> None:
    send_discord_message(message)


def notify_stop(message: str) -> None:
    send_discord_message(message)


def notify_summary(message: str) -> None:
    send_discord_message(message)

