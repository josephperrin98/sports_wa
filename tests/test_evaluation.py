import csv
import io
import json
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app import evaluation, service

NEW_YORK = ZoneInfo("America/New_York")
REPLY = (
    "Inter v Milan - 2:45 PM ET\n"
    "Channels: DAZN / Sky Sport (Italy)\n"
    "Derby with the title at stake.\n"
    "\n"
    "Cowboys at Packers - 8:20 PM ET\n"
    "Channels: NBC / Peacock (USA)\n"
    "\n"
    "Wildcard: Kok boru (Kyrgyzstan) - league final (replay)\n"
    "Watch: KTRK YouTube channel"
)


def entry(record: dict) -> dict:
    """A log entry as gcloud prints it, with the prefix Python's logging adds."""
    return {"textPayload": f"INFO:app.service:answer_log {json.dumps(record)}"}


def record(time="2026-10-18T18:30:00+00:00", reply=REPLY):
    return {"time": time, "question": "what's on?", "region": "Central Asia", "reply": reply}


class RecordsTest(unittest.TestCase):
    def test_keeps_only_answer_lines_oldest_first(self):
        entries = [
            entry(record(time="2026-10-18T20:00:00+00:00")),
            {"textPayload": "INFO:app.claude:claude model=claude-opus-5-5 est_cost_usd=0.412"},
            {"jsonPayload": {"message": "a request log"}},
            entry(record(time="2026-10-18T18:30:00+00:00")),
        ]

        times = [r["time"] for r in evaluation.records(entries)]

        self.assertEqual(times, ["2026-10-18T18:30:00+00:00", "2026-10-18T20:00:00+00:00"])

    def test_reads_back_what_the_service_logs(self):
        # The two halves of the evaluation must agree on the line's format.
        with self.assertLogs("app.service", level="INFO") as logs:
            service.log_answer(datetime(2026, 10, 18, 18, 30, tzinfo=timezone.utc), "what's on?", "East Asia", "Hé")

        found = evaluation.records([{"textPayload": f"INFO:app.service:{logs.records[-1].getMessage()}"}])

        self.assertEqual(found[0]["region"], "East Asia")
        self.assertEqual(found[0]["reply"], "Hé")


class RowTest(unittest.TestCase):
    def test_counts_events_and_wildcard_from_the_reply_format(self):
        row = evaluation.row(record(), NEW_YORK)

        self.assertEqual(row["time"], "2026-10-18 14:30")
        self.assertEqual(row["events_listed"], 2)
        self.assertEqual(row["has_wildcard"], "y")

    def test_leaves_the_checks_for_me_to_fill(self):
        row = evaluation.row(record(), NEW_YORK)

        self.assertEqual([row[c] for c in evaluation.TO_FILL], ["", "", "", "", ""])

    def test_an_apology_has_no_events_and_no_wildcard(self):
        row = evaluation.row(record(reply=service.SORRY), NEW_YORK)

        self.assertEqual((row["events_listed"], row["has_wildcard"]), (0, "n"))


class WriteCsvTest(unittest.TestCase):
    def test_one_row_per_answer_and_the_reply_survives_its_line_breaks(self):
        out = io.StringIO()

        evaluation.write_csv([entry(record())], out, NEW_YORK)

        rows = list(csv.DictReader(io.StringIO(out.getvalue())))
        self.assertEqual(len(rows), 1)
        self.assertEqual(list(rows[0]), evaluation.COLUMNS)
        self.assertEqual(rows[0]["reply"], REPLY)


if __name__ == "__main__":
    unittest.main()
