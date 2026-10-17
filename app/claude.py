"""Calls the Claude Messages API over HTTPS using only the standard library.

Knows the API's request and response format. Knows nothing about sport or WhatsApp.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-opus-5-5"
MAX_CONTINUATIONS = 3  # how many times we resume a turn the server paused mid-search
TIMEOUT_SECONDS = 120  # a search-heavy answer can take a minute or more

# List prices in US$, checked 2026-10-17. Only used for the cost estimate in the logs.
PRICE_PER_INPUT_TOKEN = 4 / 1_000_000
PRICE_PER_OUTPUT_TOKEN = 20 / 1_000_000
PRICE_PER_SEARCH = 10 / 1_000

log = logging.getLogger(__name__)


class ClaudeError(Exception):
    """The API call failed or gave no usable answer."""


def ask(system: str, user_text: str, send=None) -> str:
    """Send one question to Claude (with web search) and return its final answer text.

    `send` posts a request body and returns the parsed response; tests pass a fake.
    """
    send = send or _post
    messages = [{"role": "user", "content": user_text}]
    responses = []
    started = time.monotonic()

    for _ in range(1 + MAX_CONTINUATIONS):
        response = send(build_request(system, messages))
        responses.append(response)
        if response["stop_reason"] != "pause_turn":
            break
        # The server paused its search loop. Sending the paused turn back resumes it.
        messages = [messages[0], {"role": "assistant", "content": response["content"]}]

    _log_usage(responses, time.monotonic() - started)

    text = final_text(response["content"])
    if response["stop_reason"] != "end_turn" or not text:
        raise ClaudeError(f"No usable answer (stop_reason={response['stop_reason']})")
    return text


def build_request(system: str, messages: list) -> dict:
    return {
        "model": MODEL,
        "max_tokens": 16000,
        "system": system,
        "messages": messages,
        "tools": [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
        "output_config": {"effort": "medium"},
        # If a safety check declines the request, the API retries it on another model.
        "fallbacks": "default",
    }


def final_text(content: list) -> str:
    """The answer is the text after Claude's last search. Text before that is its working."""
    parts = []
    for block in content:
        if block["type"] == "text":
            parts.append(block["text"])
        elif block["type"] in ("server_tool_use", "web_search_tool_result"):
            parts = []
    # Citations split one answer into several text blocks, so join without separators.
    return "".join(parts).strip()


def _post(body: dict) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ClaudeError("ANTHROPIC_API_KEY is not set")
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "server-side-fallback-2026-07-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        # The body is the API's JSON explanation of the error. It never contains the key.
        detail = e.read().decode("utf-8", "replace")[:500]
        raise ClaudeError(f"API returned {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ClaudeError(f"Could not reach the API: {e}") from e


def _log_usage(responses: list, seconds: float) -> None:
    usages = [r.get("usage", {}) for r in responses]
    input_tokens = sum(u.get("input_tokens", 0) for u in usages)
    output_tokens = sum(u.get("output_tokens", 0) for u in usages)
    searches = sum(u.get("server_tool_use", {}).get("web_search_requests", 0) for u in usages)
    cost = (
        input_tokens * PRICE_PER_INPUT_TOKEN
        + output_tokens * PRICE_PER_OUTPUT_TOKEN
        + searches * PRICE_PER_SEARCH
    )
    log.info(
        "claude model=%s requests=%d seconds=%.1f input_tokens=%d output_tokens=%d "
        "web_searches=%d est_cost_usd=%.3f",
        responses[-1].get("model", MODEL), len(responses), seconds,
        input_tokens, output_tokens, searches, cost,
    )
