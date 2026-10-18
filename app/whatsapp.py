"""Twilio-specific WhatsApp details: reading incoming webhooks, replying, and sending messages.

Everything that knows Twilio's formats lives here, so moving to another provider
(e.g. Meta's Cloud API) means changing this module only.
"""

import base64
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode
from xml.sax.saxutils import escape

MAX_BODY_CHARS = 1600  # Twilio rejects longer messages


@dataclass(frozen=True)
class IncomingMessage:
    sender: str  # e.g. "whatsapp:+33600000000"
    text: str
    message_id: str  # Twilio's MessageSid, unique per message


def parse_incoming(form_body: bytes) -> IncomingMessage:
    """Turn Twilio's form-encoded webhook body into an IncomingMessage."""
    fields = parse_qs(form_body.decode("utf-8"), keep_blank_values=True)

    def first(name: str) -> str:
        return fields.get(name, [""])[0]

    return IncomingMessage(sender=first("From"), text=first("Body"), message_id=first("MessageSid"))


def build_reply(text: str) -> str:
    """Build the TwiML (Twilio's XML format) that tells Twilio to send `text` back.

    An empty `text` gives an empty response, which tells Twilio to send nothing.
    """
    message = f"<Message>{escape(text)}</Message>" if text else ""
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{message}</Response>'


def send_message(to: str, text: str, open_url=urllib.request.urlopen) -> None:
    """Send a WhatsApp message through Twilio's REST API.

    Used for answers that take longer than Twilio waits for a webhook reply.
    `open_url` sends the request; tests pass a fake.
    """
    sid, token = os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]
    fields = {"From": os.environ["TWILIO_WHATSAPP_FROM"], "To": to, "Body": text[:MAX_BODY_CHARS]}
    request = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data=urlencode(fields).encode("utf-8"),
        headers={"Authorization": "Basic " + base64.b64encode(f"{sid}:{token}".encode()).decode()},
        method="POST",
    )
    try:
        with open_url(request, timeout=30):
            pass
    except urllib.error.HTTPError as e:
        # Twilio's error body names the problem (e.g. an unjoined sandbox number).
        raise RuntimeError(f"Twilio returned {e.code}: {e.read().decode('utf-8', 'replace')[:500]}") from e
