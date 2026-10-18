import importlib.util
import unittest
from unittest import mock

from app import service, whatsapp

# Skipped where FastAPI isn't installed, so the other tests can still run there.
HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None

ME = "whatsapp:+33600000000"
BODY = b"From=whatsapp%3A%2B33600000000&Body=hello&MessageSid=SM1"


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class WhatsAppWebhookTest(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from app.main import app

        self.client = TestClient(app)
        env = mock.patch.dict("os.environ", {"TWILIO_AUTH_TOKEN": "test-token", "MY_WHATSAPP_NUMBER": ME})
        env.start()
        self.addCleanup(env.stop)
        # A fresh, empty answer box for each test.
        box = mock.patch("app.service.BOX", service.AnswerBox())
        box.start()
        self.addCleanup(box.stop)

    def post(self, body, signature=None):
        if signature is None:
            # TestClient calls the app as "testserver", so that's the URL Twilio would have signed.
            signature = whatsapp.sign("https://testserver/webhook/whatsapp", body, "test-token")
        return self.client.post(
            "/webhook/whatsapp",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "X-Twilio-Signature": signature},
        )

    def test_acks_at_once_then_the_next_message_collects_the_answer(self):
        # Stand in for Claude so the test never calls the API.
        with mock.patch("app.service.reply_to", return_value="Inter v Milan") as reply_to:
            first = self.post(BODY)
            # TestClient runs background tasks before returning, so the answer is already waiting.
            second = self.post(BODY)

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.headers["content-type"].startswith("application/xml"))
        self.assertIn("<Message>On it", first.text)
        self.assertIn("<Message>Inter v Milan</Message>", second.text)
        reply_to.assert_called_once_with("hello")

    def test_rejects_a_request_without_a_valid_twilio_signature(self):
        with mock.patch("app.service.answer") as answer:
            response = self.post(BODY, signature="forged=")

        self.assertEqual(response.status_code, 403)
        answer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
