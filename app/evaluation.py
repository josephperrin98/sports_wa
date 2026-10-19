"""Turns the answer log into a CSV sheet, one row per answer, for checking by hand.

In Cloud Shell, from the project folder:

    gcloud logging read 'resource.labels.service_name="sports-wa" AND textPayload:"answer_log"' \
        --freshness=30d --format=json | python3 -m app.evaluation > answers.csv
"""

import csv
import json
import sys
from datetime import datetime, tzinfo
from zoneinfo import ZoneInfo

from app import preferences, service

# Filled in by hand after checking each answer (see the README).
TO_FILL = ["events_on_today", "channels_correct", "ranking_ok", "wildcard_watchable", "notes"]
COLUMNS = ["time", "question", "region", "events_listed", "has_wildcard", *TO_FILL, "reply"]


def records(entries: list) -> list[dict]:
    """The answers in gcloud's JSON output, oldest first. Other log lines are skipped."""
    marker = service.ANSWER_LOG + " "
    found = []
    for entry in entries:
        # Python's logging puts "INFO:app.service:" in front, so look for the marker.
        text = entry.get("textPayload", "")
        start = text.find(marker)
        if start != -1:
            found.append(json.loads(text[start + len(marker):]))
    return sorted(found, key=lambda record: record["time"])


def row(record: dict, tz: tzinfo) -> dict:
    """What can be counted from the reply's format is filled in; the rest is left to me."""
    lines = record["reply"].splitlines()
    return {
        "time": datetime.fromisoformat(record["time"]).astimezone(tz).strftime("%Y-%m-%d %H:%M"),
        "question": record["question"],
        "region": record["region"],
        "events_listed": sum(line.startswith("Channels:") for line in lines),
        "has_wildcard": "y" if any(line.startswith("Wildcard:") for line in lines) else "n",
        **{column: "" for column in TO_FILL},
        "reply": record["reply"],
    }


def write_csv(entries: list, out, tz: tzinfo) -> None:
    writer = csv.DictWriter(out, fieldnames=COLUMNS)
    writer.writeheader()
    for record in records(entries):
        writer.writerow(row(record, tz))


if __name__ == "__main__":
    # Times in my time zone, as in the replies.
    write_csv(json.load(sys.stdin), sys.stdout, ZoneInfo(preferences.load()["timezone"]))
