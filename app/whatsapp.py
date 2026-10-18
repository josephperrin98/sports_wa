"""Twilio-specific WhatsApp details: reading incoming webhooks, replying, and sending messages.

Everything that knows Twilio's formats lives here, so moving to another provider
(e.g. Meta's Cloud API) means changing this module only.
"""

import base64
import hashlib
import hmac
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


def webhook_url(host: str, path: str) -> str:
    """The public URL Twilio called, which is what Twilio signs.

    Cloud Run receives requests over plain HTTP behind its HTTPS front door, so the app
    sees the wrong scheme. The Host header and the path are right.
    """
    return f"https://{host}{path}"


def sign(url: str, form_body: bytes, auth_token: str) -> str:
    """Twilio's signature: the URL followed by every parameter name and value (sorted by
    name, no separators), hashed with HMAC-SHA1 keyed with the auth token, in base64."""
    fields = parse_qs(form_body.decode("utf-8"), keep_blank_values=True)
    text = url + "".join(name + value for name in sorted(fields) for value in sorted(set(fields[name])))
    digest = hmac.new(auth_token.encode("utf-8"), text.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def is_from_twilio(url: str, form_body: bytes, signature: str) -> bool:
    """True only if the X-Twilio-Signature header proves Twilio sent this request.

    Anyone can find the URL, but only Twilio and this app know the auth token.
    """
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not auth_token or not signature:
        return False
    # compare_digest takes the same time however many characters match, so timing
    # doesn't reveal how close a forged signature was.
    return hmac.compare_digest(sign(url, form_body, auth_token).encode(), signature.encode())


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
