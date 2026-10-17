"""Twilio-specific WhatsApp details: reading incoming webhooks and building replies.

Everything that knows Twilio's formats lives here, so moving to another provider
(e.g. Meta's Cloud API) means changing this module only.
"""

from dataclasses import dataclass
from urllib.parse import parse_qs
from xml.sax.saxutils import escape


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
    """Build the TwiML (Twilio's XML format) that tells Twilio to send `text` back."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escape(text)}</Message></Response>"
    )
