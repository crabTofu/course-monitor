import json
import os
import time

import requests
from dotenv import load_dotenv

from watcher import build_list_message, get_watchers


load_dotenv(".env")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OFFSET = 0


def send_telegram_message(text, chat_id=None):
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    target_chat = chat_id or CHAT_ID
    if not target_chat:
        raise RuntimeError("TELEGRAM_CHAT_ID is missing")

    response = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": target_chat, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def poll_updates():
    global OFFSET
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"offset": OFFSET, "timeout": 30}
    response = requests.get(url, params=params, timeout=40)
    response.raise_for_status()
    payload = response.json()

    for update in payload.get("result", []):
        update_id = update.get("update_id")
        message = update.get("message") or {}
        if not message:
            continue

        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")

        if text.lower() in {"list", "/list", "check", "/check"}:
            reply = build_list_message()
            send_telegram_message(reply, chat_id)

        OFFSET = max(OFFSET, int(update_id) + 1)


def main():
    if not TOKEN:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN in your environment or .env")

    print("Telegram bot started. Listening for /list commands...")
    while True:
        try:
            poll_updates()
        except Exception as exc:
            print(f"Telegram poll error: {exc}")
        time.sleep(2)


if __name__ == "__main__":
    main()
