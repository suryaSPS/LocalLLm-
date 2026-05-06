#!/usr/bin/env python3
"""
Daily summary cron job.

Run at 23:00 each day:
  crontab -e
  0 23 * * * cd /path/to/gym-assistant && python scripts/daily_summary.py

Generates a journal entry summarising the day and appends it to
data/journal.txt via the local LLM.
"""
import sys
import os

# Allow running from repo root without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server.db import get_today_workout, get_today_meals, get_week_summary
from server.context import _format_today_workout, _format_week_summary, _format_meals
from server.ollama_client import chat_stream

JOURNAL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "journal.txt")


def build_summary_prompt():
    today_workout = get_today_workout()
    week_summary  = get_week_summary()
    today_meals   = get_today_meals()

    return f"""You are a concise training journal. Write a 3-5 sentence summary of today's workout and diet.
Compare to last week where relevant. Flag any PRs (personal records). Do not use bullet points.

Today's workout:
{_format_today_workout(today_workout)}

Last 7 days:
{_format_week_summary(week_summary)}

Diet today:
{_format_meals(today_meals)}
"""


def run():
    from datetime import date

    prompt = build_summary_prompt()
    messages = [
        {"role": "system", "content": "You write concise training journal entries."},
        {"role": "user", "content": prompt},
    ]

    print("Generating daily summary…")
    chunks = []
    for chunk in chat_stream(messages):
        print(chunk, end="", flush=True)
        chunks.append(chunk)
    print()

    summary = "".join(chunks).strip()
    entry = f"\n\n--- {date.today().isoformat()} ---\n{summary}\n"

    os.makedirs(os.path.dirname(JOURNAL_PATH), exist_ok=True)
    with open(JOURNAL_PATH, "a") as f:
        f.write(entry)

    print(f"\nAppended to {JOURNAL_PATH}")


if __name__ == "__main__":
    run()
