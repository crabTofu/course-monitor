import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None


STATE_FILE = Path(__file__).with_name("state.json")
DEFAULT_CONFIG = [
    {
        "name": "BetterFlow adult level 3",
        "url": "https://betterflow.courseprogress.co.uk/onlinejoining/classes-results?filter=%7B%22showFullCourses%22:false,%22region%22:81,%22courseGroupCategory%22:%5B2%5D,%22centre%22:317,%22courseType%22:1,%22levelGroup2%22:%5B%224:%7C%2Ftennis-adult%22%5D%7D",
        "frequency_minutes": 720,
        "match_terms": ["adult", "level 3"],
        "start_time": "18:00",
        "end_time": "20:00",
    }
]


def load_env_file():
    load_dotenv(Path(__file__).with_name(".env"))


def parse_time_to_minutes(value):
    if value is None:
        return None
    value = str(value).strip().lower()

    if "pm" in value or "am" in value:
        match = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)", value)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            period = match.group(3)
            if period == "pm" and hour != 12:
                hour += 12
            if period == "am" and hour == 12:
                hour = 0
            return hour * 60 + minute
        return None

    match = re.search(r"(\d{1,2}):(\d{2})", value)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        return hour * 60 + minute

    return None


def find_matching_slots(text, match_terms, start_time, end_time):
    if not isinstance(match_terms, list) or not match_terms:
        match_terms = []

    lowered = text.lower()
    if any(term.lower() not in lowered for term in match_terms):
        return []

    start_minutes = parse_time_to_minutes(start_time)
    end_minutes = parse_time_to_minutes(end_time)
    if start_minutes is None or end_minutes is None:
        return []

    time_candidates = re.findall(r"\d{1,2}:\d{2}\s*(?:am|pm)?", lowered)
    if not time_candidates:
        return []

    matches = []
    # Split the page body into plausible blocks for slot detection.
    blocks = re.split(r"\n\s*\n+|\|\s*", text)
    for block in blocks:
        block_lower = block.lower()
        if not block_lower:
            continue
        if not all(term.lower() in block_lower for term in match_terms):
            continue
        for candidate in time_candidates:
            candidate_minutes = parse_time_to_minutes(candidate)
            if candidate_minutes is None:
                continue
            if start_minutes <= candidate_minutes <= end_minutes:
                matches.append(block.strip())
                break
    return matches


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_page_text(url):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        html = response.text
        if html and "<" in html:
            return html
    except Exception:
        pass

    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed; cannot render JavaScript page content.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        text = page.locator("body").inner_text()
        browser.close()
        return text


def extract_plain_text(html_or_text):
    if not html_or_text:
        return ""
    if "<" not in html_or_text:
        return html_or_text
    text = re.sub(r"<script.*?</script>", " ", html_or_text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def send_telegram_message(message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram not configured; skipping notification.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "disable_web_page_preview": True}
    response = requests.post(url, data=payload, timeout=20)
    response.raise_for_status()
    print("Telegram notification sent.")


def parse_watchers(raw_watchers):
    if isinstance(raw_watchers, str):
        raw_watchers = json.loads(raw_watchers)
    if not isinstance(raw_watchers, list):
        return []
    return raw_watchers


def get_watchers():
    load_env_file()
    raw_watchers = os.getenv("WATCHERS_JSON")
    if raw_watchers:
        watchers = parse_watchers(raw_watchers)
    else:
        watchers = DEFAULT_CONFIG
    return watchers


def monitor_once(dry_run=False):
    state = load_state()
    watchers = get_watchers()
    alerts = []

    for watcher in watchers:
        name = watcher.get("name", "Unnamed watcher")
        url = watcher.get("url")
        if not url:
            continue
        try:
            raw_html = fetch_page_text(url)
        except Exception as exc:
            print(f"Failed for {name}: {exc}")
            continue

        text = extract_plain_text(raw_html)
        matches = find_matching_slots(
            text,
            watcher.get("match_terms", ["adult", "level 3"]),
            watcher.get("start_time", "18:00"),
            watcher.get("end_time", "20:00"),
        )

        if not matches:
            print(f"{name}: no matching slot found")
            continue

        unique_matches = [m for m in matches if m not in state.get(name, [])]
        if not unique_matches:
            print(f"{name}: matching slots already seen")
            continue

        message = f"{name}\n\n{chr(10).join(unique_matches[:5])}"
        alerts.append(message)
        print(f"{name}: new availability detected")
        state[name] = matches

        if not dry_run:
            send_telegram_message(message)

    save_state(state)
    return alerts


def run_scheduler(interval_minutes=60):
    while True:
        print(f"[{datetime.now().isoformat(timespec='seconds')}] Checking watchers...")
        monitor_once(dry_run=False)
        time.sleep(interval_minutes * 60)


def main():
    parser = argparse.ArgumentParser(description="Monitor pages for course availability.")
    parser.add_argument("--dry-run", action="store_true", help="Check pages and print results without sending Telegram messages.")
    parser.add_argument("--once", action="store_true", help="Run one check and exit.")
    parser.add_argument("--interval-minutes", type=int, default=60, help="How often to retry when running in loop mode.")
    args = parser.parse_args()

    if args.once or args.dry_run:
        monitor_once(dry_run=args.dry_run)
        return

    run_scheduler(interval_minutes=args.interval_minutes)


if __name__ == "__main__":
    main()
