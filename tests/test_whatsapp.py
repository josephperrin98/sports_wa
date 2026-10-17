import unittest

from app.whatsapp import IncomingMessage, build_reply, parse_incoming


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


if __name__ == "__main__":
    unittest.main()
