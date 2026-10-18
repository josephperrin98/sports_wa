import importlib.util
import unittest
from unittest import mock

# Skipped where FastAPI isn't installed, so the other tests can still run there.
HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class WhatsAppWebhookTest(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from app.main import app

        self.client = TestClient(app)

    def test_acks_at_once_and_answers_in_the_background(self):
        # Stand in for the slow answer so the test never calls Claude or Twilio.
        with mock.patch("app.service.answer") as answer:
            response = self.client.post(
                "/webhook/whatsapp",
                content=b"From=whatsapp%3A%2B33600000000&Body=hello&MessageSid=SM1",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/xml"))
        self.assertIn("<Message>On it", response.text)
        # TestClient runs background tasks before returning, so the call is already recorded.
        answer.assert_called_once()
        self.assertEqual(answer.call_args.args[:2], ("whatsapp:+33600000000", "hello"))


if __name__ == "__main__":
    unittest.main()
