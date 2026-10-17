import unittest

from app.service import reply_to


class ReplyToTest(unittest.TestCase):
    def test_echoes_the_message(self):
        self.assertEqual(reply_to("what's on?"), "Echo: what's on?")

    def test_empty_message_gets_a_hint_instead_of_an_empty_echo(self):
        # A photo or voice note arrives with an empty Body.
        self.assertEqual(reply_to("   "), "I can only read text messages for now.")


if __name__ == "__main__":
    unittest.main()
