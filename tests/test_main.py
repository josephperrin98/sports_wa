import importlib.util
import unittest
from unittest import mock

from app import whatsapp

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

    def post(self, body, signature=None):
        if signature is None:
            # TestClient calls the app as "testserver", so that's the URL Twilio would have signed.
            signature = whatsapp.sign("https://testserver/webhook/whatsapp", body, "test-token")
        return self.client.post(
            "/webhook/whatsapp",
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded", "X-Twilio-Signature": signature},
        )

    def test_acks_at_once_and_answers_in_the_background(self):
        # Stand in for the slow answer so the test never calls Claude or Twilio.
        with mock.patch("app.service.answer") as answer:
            response = self.post(BODY)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/xml"))
        self.assertIn("<Message>On it", response.text)
        # TestClient runs background tasks before returning, so the call is already recorded.
        answer.assert_called_once()
        self.assertEqual(answer.call_args.args[:2], (ME, "hello"))

    def test_rejects_a_request_without_a_valid_twilio_signature(self):
        with mock.patch("app.service.answer") as answer:
            response = self.post(BODY, signature="forged=")

        self.assertEqual(response.status_code, 403)
        answer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
