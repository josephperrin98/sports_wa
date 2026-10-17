import importlib.util
import unittest

# Skipped where FastAPI isn't installed, so the other tests can still run there.
HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class WhatsAppWebhookTest(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from app.main import app

        self.client = TestClient(app)

    def test_replies_to_a_twilio_webhook_with_a_twiml_echo(self):
        response = self.client.post(
            "/webhook/whatsapp",
            content=b"From=whatsapp%3A%2B33600000000&Body=hello&MessageSid=SM1",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/xml"))
        self.assertIn("<Message>Echo: hello</Message>", response.text)


if __name__ == "__main__":
    unittest.main()
