# Course Monitor

A lightweight Python watcher for booking pages and course availability checks.

## Features

- monitor multiple pages
- configurable per-page check frequency
- optional Telegram alerts
- simple JSON state to avoid duplicate notifications
- dry-run mode for testing without sending messages

## Quick start

1. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your values.
4. Run once in dry-run mode:
   ```bash
   python watcher.py --dry-run
   ```
5. Run the scheduler:
   ```bash
   python watcher.py
   ```

## Configuration

The `WATCHERS_JSON` environment variable is a JSON array of watcher objects. Each object supports:

- `name`: friendly description
- `url`: page to check
- `frequency_minutes`: how often to poll this page
- `match_terms`: text terms that must be present
- `start_time`: start of acceptable time range, e.g. `18:00`
- `end_time`: end of acceptable time range, e.g. `20:00`

## Example watcher

```json
[
  {
    "name": "BetterFlow adult level 3",
    "url": "https://example.com/classes",
    "frequency_minutes": 720,
    "match_terms": ["adult", "level 3"],
    "start_time": "18:00",
    "end_time": "20:00"
  }
]
```

## Telegram setup

1. Create a bot with BotFather.
2. Get your bot token and chat ID.
3. Put them in `.env`.
4. The monitor will send messages when a new matching slot appears.

## Notes

This project intentionally keeps the logic simple so it is easy to host on a small VPS, Raspberry Pi, or GitHub Actions schedule.
