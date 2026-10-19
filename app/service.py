"""Decides what to reply. Knows nothing about Twilio or HTTP."""

import json
import logging
import os
import random
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app import claude, preferences

log = logging.getLogger(__name__)

EMPTY_HINT = "I can only read text messages for now."
ACK = "On it, checking what's on. Send me any message in about a minute to get the answer."
STILL_CHECKING = "Still checking. Send me another message in about 30 seconds."
SORRY = "Sorry, I couldn't check what's on right now. Try again in a minute."
ANSWER_LOG = "answer_log"  # marks the evaluation lines, so app/evaluation.py can find them

SYSTEM_PROMPT = """\
You are a sports curator on WhatsApp for one person. When they ask what's on, use web \
search to find today's events that match their preferences below, and tell \
them which channel to watch each one on.

Scope: you only help find sport to watch. If a message is about anything else, reply in \
one short sentence that you only help find sport to watch, and don't answer it.

How to search, in this order. You have {searches} searches at most, so plan them:
1. About 3 broad searches for today's schedule, starting with the teams I follow and \
tier 1, then lower tiers only if needed to fill the reply.
2. Pick the shortlist of events for the reply. Don't spend searches on anything else, \
like events that have ended or other days.
3. About one search per shortlisted event for its channels, in the event's language \
(rules below), for that country's broadcaster. For example, search in Italian for the \
Italian broadcaster of a Serie A match.
4. Two or three searches for the wildcard, until you find one I can watch now.
Fixtures, scores and channels change all the time, so look them up now. Never answer from \
memory. Only list an event a search result shows is on today. If you can't find its \
channel, write "channel not found" rather than guessing.

Ranking: a team I follow comes first, then a higher tier. Within a tier, the most \
compelling event right now comes first (close score, decider, final stage, derby).

Reply in plain text, no Markdown, under 1,400 characters. One short block per event, \
exactly three lines:
<event> - <score and minute, or kick-off time>
Channels: <channel> / <channel> (<country>)
<one line on why it's worth watching>
Then the wildcard, exactly two lines:
Wildcard: <sport> (<country>) - <event, and when, or (replay)>
Watch: <channel or stream, never "not found">
Write every line in your own words. Never copy or quote text from search results.
The "why" line is a real reason: a rivalry, the league table, form, a key player, what's \
at stake. If you can't find one, leave the line out rather than filling it.
If nothing is on today, say so in one line first. No other introduction or sign-off, no \
links, and never mention your searches, search limits, or events that have ended.

Preferences:
{preferences}
"""


@dataclass(frozen=True)
class Plan:
    reply_now: str  # sent straight back in the webhook response ("" sends nothing)
    answer_later: bool  # whether to start asking Claude in the background


class AnswerBox:
    """Holds the one answer being prepared for me until my next message collects it.

    Twilio's trial account can only reply to a message, not send one later, and Claude
    takes longer than Twilio waits for a reply. So the answer waits here, in memory.
    With a single Cloud Run instance that's enough: a restart only means asking again.
    """

    ANSWER_KEEPS_FOR = timedelta(minutes=10)  # after that, "what's live" is out of date
    SEARCH_GIVES_UP_AFTER = timedelta(minutes=5)  # a search this old has died somewhere

    def __init__(self):
        # The webhook and the background search run on different threads.
        self._lock = threading.Lock()
        self._searching_since: datetime | None = None
        self._answer: str | None = None
        self._answered_at: datetime | None = None

    def claim(self, now: datetime) -> tuple[str, str]:
        """Collect the waiting answer, or report a search in progress, or start one.

        Returns ("answer", text), ("searching", "") or ("start", ""). Checking and
        claiming happen under one lock, so a search finishing in between can't be lost.
        """
        with self._lock:
            if self._answer is not None and now - self._answered_at < self.ANSWER_KEEPS_FOR:
                text, self._answer = self._answer, None
                return "answer", text
            if self._searching_since is not None and now - self._searching_since < self.SEARCH_GIVES_UP_AFTER:
                return "searching", ""
            self._searching_since, self._answer = now, None
            return "start", ""

    def fill(self, text: str, now: datetime) -> None:
        with self._lock:
            self._searching_since, self._answer, self._answered_at = None, text, now


BOX = AnswerBox()


def plan_for(sender: str, text: str, now: datetime | None = None, box: AnswerBox | None = None) -> Plan:
    """Decide what to reply within Twilio's time limit, before any slow work."""
    if sender != os.environ.get("MY_WHATSAPP_NUMBER"):
        # Every answer costs money, so only my number gets one. No reply at all to others.
        log.warning("Ignored a message from a number that isn't mine")
        return Plan("", answer_later=False)
    if not text.strip():
        return Plan(EMPTY_HINT, answer_later=False)
    status, waiting = (box or BOX).claim(now or datetime.now(timezone.utc))
    if status == "answer":
        return Plan(waiting, answer_later=False)
    if status == "searching":
        return Plan(STILL_CHECKING, answer_later=False)
    return Plan(ACK, answer_later=True)


def answer(text: str, now: datetime | None = None, box: AnswerBox | None = None) -> None:
    """Runs after Twilio has had its quick reply: ask Claude and leave the answer in the box.

    Nobody is waiting on this function, so an unexpected error still fills the box,
    with an apology, rather than leaving my next message stuck on "still checking".
    """
    try:
        reply = reply_to(text)
    except Exception:
        log.exception("Couldn't prepare the answer")
        reply = SORRY
    (box or BOX).fill(reply, now or datetime.now(timezone.utc))


def reply_to(text: str, now: datetime | None = None, ask=claude.ask, pick=random.choice) -> str:
    if not text.strip():
        return EMPTY_HINT
    now = now or datetime.now(timezone.utc)
    prefs = preferences.load()
    system = SYSTEM_PROMPT.format(preferences=preferences.to_prompt(prefs), searches=claude.MAX_SEARCHES)
    # The time and the wildcard region go in the message, not the system prompt, so the
    # system prompt never changes. The region is picked here because Claude can't vary
    # its choice on its own: it never sees its past replies.
    region = pick(prefs["wildcard"]["regions"])
    question = f"Current time (UTC): {now:%Y-%m-%d %H:%M}\nWildcard region: {region}\n\n{text}"
    try:
        reply = ask(system, question)
    except claude.ClaudeError:
        log.exception("Claude call failed")
        reply = SORRY
    log_answer(now, text, region, reply)
    return reply


def log_answer(now: datetime, question: str, region: str, reply: str) -> None:
    """One JSON line per answer, for the evaluation week.

    Cloud Logging keeps it for 30 days. A file wouldn't survive: the container's disk
    is wiped whenever it restarts.
    """
    record = {"time": now.isoformat(), "question": question, "region": region, "reply": reply}
    log.info("%s %s", ANSWER_LOG, json.dumps(record, ensure_ascii=False))
