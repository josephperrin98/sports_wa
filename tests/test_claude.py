import os
import unittest
from unittest import mock

from app import claude


def response(stop_reason, content, usage=None):
    return {"stop_reason": stop_reason, "content": content, "usage": usage or {}}


SEARCH = [
    {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {"query": "serie a"}},
    {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": []},
]


class FakeSend:
    """Stands in for the HTTP call: returns canned responses and records each request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, body):
        self.requests.append(body)
        return self.responses.pop(0)


class AskTest(unittest.TestCase):
    def test_returns_the_text_after_the_last_search(self):
        content = [{"type": "text", "text": "Let me search."}, *SEARCH,
                   {"type": "text", "text": "Inter v Milan"}, {"type": "text", "text": " - live"}]
        send = FakeSend(response("end_turn", content))

        answer = claude.ask("system", "what's on?", send=send)

        self.assertEqual(answer, "Inter v Milan - live")

    def test_sends_model_system_question_and_web_search_tool(self):
        send = FakeSend(response("end_turn", [{"type": "text", "text": "ok"}]))

        claude.ask("be a curator", "what's on?", send=send)

        body = send.requests[0]
        self.assertEqual(body["model"], claude.MODEL)
        self.assertEqual(body["system"], "be a curator")
        self.assertEqual(body["messages"], [{"role": "user", "content": "what's on?"}])
        self.assertEqual(body["tools"][0]["type"], "web_search_20260209")

    def test_resumes_a_paused_turn_by_sending_it_back(self):
        send = FakeSend(response("pause_turn", SEARCH),
                        response("end_turn", [{"type": "text", "text": "done"}]))

        answer = claude.ask("system", "what's on?", send=send)

        self.assertEqual(answer, "done")
        resumed = send.requests[1]["messages"]
        self.assertEqual(resumed[0], {"role": "user", "content": "what's on?"})
        self.assertEqual(resumed[1], {"role": "assistant", "content": SEARCH})
        self.assertEqual(send.requests[1]["tools"], send.requests[0]["tools"])

    def test_gives_up_after_too_many_pauses(self):
        send = FakeSend(*[response("pause_turn", SEARCH)] * (1 + claude.MAX_CONTINUATIONS))

        with self.assertLogs("app.claude"), self.assertRaises(claude.ClaudeError):
            claude.ask("system", "what's on?", send=send)

        self.assertEqual(len(send.requests), 1 + claude.MAX_CONTINUATIONS)

    def test_a_refusal_is_an_error_not_an_answer(self):
        send = FakeSend(response("refusal", []))

        with self.assertLogs("app.claude"), self.assertRaises(claude.ClaudeError):
            claude.ask("system", "what's on?", send=send)

    def test_logs_tokens_searches_and_estimated_cost(self):
        usage = {"input_tokens": 10_000, "output_tokens": 1_000, "server_tool_use": {"web_search_requests": 2}}
        send = FakeSend(response("end_turn", [{"type": "text", "text": "ok"}], usage))

        with self.assertLogs("app.claude", level="INFO") as logs:
            claude.ask("system", "what's on?", send=send)

        # 10,000 x $4/M + 1,000 x $20/M + 2 x $0.01 = $0.04 + $0.02 + $0.02
        self.assertIn("input_tokens=10000 output_tokens=1000 web_searches=2 est_cost_usd=0.080", logs.output[0])


class PostTest(unittest.TestCase):
    def test_missing_api_key_fails_before_any_network_call(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(claude.ClaudeError):
            claude._post({})


if __name__ == "__main__":
    unittest.main()
