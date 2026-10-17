"""Decides what to reply. Knows nothing about Twilio or HTTP."""


def reply_to(text: str) -> str:
    if not text.strip():
        return "I can only read text messages for now."
    return f"Echo: {text}"
