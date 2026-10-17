import unittest
from datetime import datetime, timezone

from app import claude, service

NOW = datetime(2026, 10, 17, 18, 30, tzinfo=timezone.utc)


class FakeAsk:
    """Stands in for claude.ask: records what it was sent and returns a canned answer."""

    def __init__(self, answer="Inter v Milan - 20:45", error=None):
        self.answer, self.error, self.calls = answer, error, []

    def __call__(self, system, question):
        self.calls.append((system, question))
        if self.error:
            raise self.error
        return self.answer


class ReplyToTest(unittest.TestCase):
    def test_asks_claude_with_preferences_time_and_question(self):
        ask = FakeAsk()

        reply = service.reply_to("what's on?", now=NOW, ask=ask)

        self.assertEqual(reply, "Inter v Milan - 20:45")
        system, question = ask.calls[0]
        self.assertIn("Serie A (tier 3)", system)
        self.assertIn("only help find sport to watch", system)
        self.assertEqual(question, "Current time (UTC): 2026-10-17 18:30\n\nwhat's on?")

    def test_empty_message_gets_a_hint_without_calling_claude(self):
        ask = FakeAsk()

        self.assertEqual(service.reply_to("   ", ask=ask), "I can only read text messages for now.")
        self.assertEqual(ask.calls, [])

    def test_a_claude_failure_becomes_a_polite_reply(self):
        ask = FakeAsk(error=claude.ClaudeError("API returned 529"))

        with self.assertLogs("app.service"):
            reply = service.reply_to("what's on?", now=NOW, ask=ask)

        self.assertIn("couldn't check what's on", reply)


if __name__ == "__main__":
    unittest.main()
