import base64
import os
import unittest
from unittest import mock
from urllib.parse import parse_qs

from app.whatsapp import IncomingMessage, build_reply, parse_incoming, send_message

TWILIO_ENV = {
    "TWILIO_ACCOUNT_SID": "AC123",
    "TWILIO_AUTH_TOKEN": "secret",
    "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
}


class ParseIncomingTest(unittest.TestCase):
    def test_reads_sender_text_and_id_from_twilio_form_body(self):
        # Same shape as Twilio's webhook: form-encoded, "+" means a space.
        body = b"From=whatsapp%3A%2B33600000000&Body=what%27s+on%3F&MessageSid=SM123"

        message = parse_incoming(body)

        self.assertEqual(
            message,
            IncomingMessage(sender="whatsapp:+33600000000", text="what's on?", message_id="SM123"),
        )

    def test_missing_fields_become_empty_strings(self):
        message = parse_incoming(b"From=whatsapp%3A%2B33600000000")

        self.assertEqual(message.text, "")
        self.assertEqual(message.message_id, "")


class BuildReplyTest(unittest.TestCase):
    def test_wraps_text_in_twiml_message(self):
        self.assertEqual(
            build_reply("Hello"),
            '<?xml version="1.0" encoding="UTF-8"?><Response><Message>Hello</Message></Response>',
        )

    def test_escapes_characters_that_would_break_the_xml(self):
        self.assertIn("<Message>PSG &lt;3 &amp; OL</Message>", build_reply("PSG <3 & OL"))

    def test_empty_text_tells_twilio_to_send_nothing(self):
        self.assertEqual(build_reply(""), '<?xml version="1.0" encoding="UTF-8"?><Response></Response>')


class SendMessageTest(unittest.TestCase):
    def send(self, text):
        sent = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_open(request, timeout):
            sent.append(request)
            return FakeResponse()

        with mock.patch.dict(os.environ, TWILIO_ENV):
            send_message("whatsapp:+33600000000", text, open_url=fake_open)
        return sent[0]

    def test_posts_from_to_and_body_to_twilio_with_basic_auth(self):
        request = self.send("Inter v Milan")

        self.assertEqual(request.full_url, "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json")
        self.assertEqual(request.get_header("Authorization"), "Basic " + base64.b64encode(b"AC123:secret").decode())
        self.assertEqual(
            parse_qs(request.data.decode()),
            {"From": ["whatsapp:+14155238886"], "To": ["whatsapp:+33600000000"], "Body": ["Inter v Milan"]},
        )

    def test_cuts_the_body_to_twilios_limit(self):
        request = self.send("x" * 2000)

        self.assertEqual(len(parse_qs(request.data.decode())["Body"][0]), 1600)


if __name__ == "__main__":
    unittest.main()
