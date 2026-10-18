import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from app import claude, service

NOW = datetime(2026, 10, 17, 18, 30, tzinfo=timezone.utc)
ME = "whatsapp:+33600000000"


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


@mock.patch.dict("os.environ", {"MY_WHATSAPP_NUMBER": ME})
class PlanForTest(unittest.TestCase):
    def setUp(self):
        self.box = service.AnswerBox()

    def plan(self, text="what's on?", minutes_later=0, sender=ME):
        return service.plan_for(sender, text, now=NOW + timedelta(minutes=minutes_later), box=self.box)

    def test_a_question_gets_a_quick_ack_and_starts_a_search(self):
        self.assertEqual(self.plan(), service.Plan(service.ACK, answer_later=True))

    def test_a_message_during_the_search_gets_still_checking_and_no_second_search(self):
        self.plan()

        self.assertEqual(self.plan("?", minutes_later=0.5), service.Plan(service.STILL_CHECKING, answer_later=False))

    def test_the_next_message_collects_the_answer_once(self):
        self.plan()
        self.box.fill("Inter v Milan", NOW + timedelta(minutes=1))

        self.assertEqual(self.plan("?", minutes_later=2), service.Plan("Inter v Milan", answer_later=False))
        self.assertEqual(self.plan("what's on?", minutes_later=3), service.Plan(service.ACK, answer_later=True))

    def test_an_answer_left_too_long_is_dropped_and_a_new_search_starts(self):
        self.plan()
        self.box.fill("Inter v Milan", NOW + timedelta(minutes=1))

        self.assertEqual(self.plan(minutes_later=12), service.Plan(service.ACK, answer_later=True))

    def test_a_search_that_never_finished_is_given_up_on(self):
        self.plan()

        self.assertEqual(self.plan(minutes_later=6), service.Plan(service.ACK, answer_later=True))

    def test_an_empty_message_gets_the_hint_and_nothing_later(self):
        self.assertEqual(self.plan(" "), service.Plan(service.EMPTY_HINT, answer_later=False))

    def test_another_number_gets_nothing_at_all(self):
        with self.assertLogs("app.service", level="WARNING"):
            plan = self.plan(sender="whatsapp:+15550001111")

        self.assertEqual(plan, service.Plan("", answer_later=False))


class AnswerTest(unittest.TestCase):
    def test_leaves_the_reply_in_the_box(self):
        box = service.AnswerBox()
        box.claim(NOW)

        with mock.patch.object(service, "reply_to", return_value="Inter v Milan"):
            service.answer("what's on?", now=NOW, box=box)

        self.assertEqual(box.claim(NOW), ("answer", "Inter v Milan"))

    def test_an_unexpected_error_leaves_an_apology_instead_of_a_stuck_search(self):
        box = service.AnswerBox()
        box.claim(NOW)

        with mock.patch.object(service, "reply_to", side_effect=RuntimeError("boom")), self.assertLogs("app.service"):
            service.answer("what's on?", now=NOW, box=box)

        self.assertEqual(box.claim(NOW), ("answer", service.SORRY))


if __name__ == "__main__":
    unittest.main()
