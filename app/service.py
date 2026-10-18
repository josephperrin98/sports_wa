"""Decides what to reply. Knows nothing about Twilio or HTTP."""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from app import claude, preferences

log = logging.getLogger(__name__)

EMPTY_HINT = "I can only read text messages for now."
ACK = "On it, checking what's on. Back in about 30 seconds."

SYSTEM_PROMPT = """\
You are a sports curator on WhatsApp for one person. When they ask what's on, use web \
search to find live or starting-soon events that match their preferences below, and tell \
them which channel to watch each one on.

Scope: you only help find sport to watch. If a message is about anything else, reply in \
one short sentence that you only help find sport to watch, and don't answer it.

How to search:
- Fixtures, scores and channels change all the time, so look them up now. Never answer \
from memory.
- Find the channel by searching in the event's language (rules below) for that country's \
broadcaster. For example, search in Italian for the Italian broadcaster of a Serie A match.
- Only list an event a search result shows is live or starting soon. If you can't find \
its channel, write "channel not found" rather than guessing.

Ranking: a higher tier comes first. Within a tier, the most compelling event right now \
comes first (close score, decider, final stage, derby).

Reply in plain text, no Markdown, under 1,000 characters. One short block per event, \
exactly three lines:
<event> - <score and minute, or day and kick-off time>
Channels: <channel> / <channel> (<country>)
<one line on why it's worth watching>
Write every line in your own words. Never copy or quote text from search results.
The "why" line is a real reason: a rivalry, the league table, form, a key player, what's \
at stake. If you can't find one, leave the line out rather than filling it.
If fewer events than asked for are live or starting soon, list those, then the next \
upcoming ones in the same format. If none are, say so in one line first. No other \
introduction or sign-off.

Preferences:
{preferences}
"""


@dataclass(frozen=True)
class Plan:
    reply_now: str  # sent straight back in the webhook response ("" sends nothing)
    answer_later: bool  # whether to ask Claude and send its answer as a second message


def plan_for(sender: str, text: str) -> Plan:
    """Decide what to do with a message within Twilio's time limit, before any slow work."""
    if sender != os.environ.get("MY_WHATSAPP_NUMBER"):
        # Every answer costs money, so only my number gets one. No reply at all to others.
        log.warning("Ignored a message from a number that isn't mine")
        return Plan("", answer_later=False)
    if not text.strip():
        return Plan(EMPTY_HINT, answer_later=False)
    return Plan(ACK, answer_later=True)


def answer(sender: str, text: str, send) -> None:
    """Runs after Twilio has had its quick reply: ask Claude, then send the answer.

    `send(to, text)` delivers the message. Nobody is waiting on this function, so errors
    are logged rather than raised.
    """
    try:
        send(sender, reply_to(text))
    except Exception:
        log.exception("Couldn't send the answer")


def reply_to(text: str, now: datetime | None = None, ask=claude.ask) -> str:
    if not text.strip():
        return EMPTY_HINT
    now = now or datetime.now(timezone.utc)
    system = SYSTEM_PROMPT.format(preferences=preferences.to_prompt(preferences.load()))
    # The time goes in the message, not the system prompt, so the system prompt never changes.
    question = f"Current time (UTC): {now:%Y-%m-%d %H:%M}\n\n{text}"
    try:
        return ask(system, question)
    except claude.ClaudeError:
        log.exception("Claude call failed")
        return "Sorry, I couldn't check what's on right now. Try again in a minute."
