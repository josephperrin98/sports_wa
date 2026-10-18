"""Loads my viewing preferences and turns them into instructions for Claude."""

import tomllib
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "preferences.toml"

MENS_ONLY = (
    "Men's teams and competitions only. A women's team with a name like one I follow "
    "doesn't count (OL Lyonnes is Lyon's women's team).\n\n"
)


def load(path: Path = DEFAULT_PATH) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def _language(entry: dict) -> str:
    """The search instruction for an entry with its own language, else nothing."""
    language = entry.get("language")
    return f": search {language} broadcasters, in {language}" if language else ""


def to_prompt(prefs: dict) -> str:
    """Render the preferences as the plain-text block that goes in the system prompt."""
    teams = "\n".join(f"- {t['name']}{_language(t)}." for t in prefs["team_boosts"])
    competitions = "\n".join(f"- {c['name']} (tier {c['tier']}){_language(c)}." for c in prefs["competitions"])
    last_tier = max(c["tier"] for c in prefs["competitions"]) + 1
    rules = "\n".join(f"{i}. {rule}" for i, rule in enumerate(prefs["language_rules"], start=1))
    wildcard = "\n".join(f"- {rule}" for rule in prefs["wildcard"]["rules"])
    label = prefs["timezone_label"]
    return (
        f"Teams I follow, shown whenever they play, in any competition, above every tier:\n{teams}\n\n"
        f"Competitions by tier (tier 1 matters most; tier 1 is always shown if on today):\n"
        f"{competitions}\n"
        f"- Anything else is tier {last_tier}: only when the tiers above can't fill the reply.\n\n"
        f"{MENS_ONLY if prefs.get('mens_only') else ''}"
        f"Tennis: {prefs['tennis_rule']}\n\n"
        f"Which language and country to search in (first rule that applies wins):\n{rules}\n\n"
        f"Wildcard, exactly one per reply, after the events:\n{wildcard}\n\n"
        f"Reply with {prefs['min_events']} to {prefs['max_events']} events plus the wildcard, "
        f"at most {prefs['max_per_sport']} events from the same sport. "
        f"Only today's events: live now, or starting before midnight in the {prefs['timezone']} time zone. "
        f"Never an event on another day, and never one that has ended. "
        f"Reach {prefs['min_events']} events by going down the tiers, to tier {last_tier} if needed, "
        f"still only today. If there are really fewer today, list those and stop. "
        f"List up to {prefs['channels_per_event']} channels per event, main one first. "
        f"Give times in the {prefs['timezone']} time zone, followed by \"{label}\" (for example 2:45 PM {label})."
    )
