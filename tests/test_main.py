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

    def test_passes_the_message_to_the_service_and_wraps_the_reply_in_twiml(self):
        # Stand in for the service so the test never calls Claude.
        with mock.patch("app.service.reply_to", side_effect=lambda text: f"got {text}"):
            response = self.client.post(
                "/webhook/whatsapp",
                content=b"From=whatsapp%3A%2B33600000000&Body=hello&MessageSid=SM1",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/xml"))
        self.assertIn("<Message>got hello</Message>", response.text)


if __name__ == "__main__":
    unittest.main()
