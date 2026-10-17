"""Loads my viewing preferences and turns them into instructions for Claude."""

import tomllib
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "preferences.toml"


def load(path: Path = DEFAULT_PATH) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def to_prompt(prefs: dict) -> str:
    """Render the preferences as the plain-text block that goes in the system prompt."""
    competitions = "\n".join(
        f"- {c['name']} (tier {c['tier']}): search {c['language']} broadcasters, in {c['language']}."
        for c in prefs["competitions"]
    )
    rules = "\n".join(f"{i}. {rule}" for i, rule in enumerate(prefs["language_rules"], start=1))
    return (
        f"Competitions I follow (tier 1 matters most):\n{competitions}\n\n"
        f"Which language and country to search in (first rule that applies wins):\n{rules}\n\n"
        f"Reply with {prefs['min_events']} to {prefs['max_events']} events, "
        f"at most {prefs['max_per_sport']} from the same sport. "
        f"List up to {prefs['channels_per_event']} channels per event, main one first. "
        f"'Starting soon' means within {prefs['starting_soon_hours']} hours. "
        f"Give times in the {prefs['timezone']} time zone."
    )
