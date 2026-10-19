import unittest

from app import preferences


class LoadTest(unittest.TestCase):
    def test_the_real_preferences_file_loads_and_renders(self):
        prompt = preferences.to_prompt(preferences.load())

        self.assertIn("- Olympique Lyonnais: search French broadcasters, in French.", prompt)
        self.assertIn("- Ligue 1 (tier 1).", prompt)
        self.assertIn("- Top 14 (tier 2): search French broadcasters, in French.", prompt)
        self.assertIn("- Serie A (tier 3).", prompt)
        self.assertIn("Anything else is tier 5", prompt)
        self.assertIn("International competitions (Champions League, Europa League) have none", prompt)
        self.assertIn("If you can't find one, pick another event in the same region", prompt)


class ToPromptTest(unittest.TestCase):
    PREFS = {
        "timezone": "Europe/Paris",
        "timezone_label": "CET",
        "mens_only": True,
        "min_events": 3,
        "max_events": 5,
        "max_per_sport": 2,
        "channels_per_event": 3,
        "language_rules": ["Rule one.", "Rule two."],
        "tennis_rule": "French players first.",
        "team_boosts": [{"name": "OGC Nice", "language": "French"}],
        "competitions": [{"name": "Ligue 1", "tier": 1}, {"name": "Top 14", "tier": 2, "language": "French"}],
        "wildcard": {"rules": ["A real event."]},
    }

    def setUp(self):
        self.prompt = preferences.to_prompt(self.PREFS)

    def test_renders_teams_above_every_tier(self):
        self.assertIn("above every tier:\n- OGC Nice: search French broadcasters, in French.", self.prompt)

    def test_competitions_name_a_language_only_when_set(self):
        self.assertIn("- Ligue 1 (tier 1).\n", self.prompt)
        self.assertIn("- Top 14 (tier 2): search French broadcasters, in French.", self.prompt)

    def test_anything_unlisted_is_the_tier_after_the_last(self):
        self.assertIn("Anything else is tier 3", self.prompt)

    def test_renders_tennis_language_rules_and_wildcard(self):
        self.assertIn("Tennis: French players first.", self.prompt)
        self.assertIn("1. Rule one.\n2. Rule two.", self.prompt)
        self.assertIn("one per reply, after the events:\n- A real event.", self.prompt)

    def test_renders_the_limits(self):
        self.assertIn("3 to 5 events plus the wildcard, at most 2 events from the same sport", self.prompt)
        self.assertIn("up to 3 channels per event, main one first", self.prompt)

    def test_only_today_and_the_minimum_comes_from_lower_tiers_not_other_days(self):
        self.assertIn("Only today's events: live now, or starting before midnight in the Europe/Paris time zone", self.prompt)
        self.assertIn("Never an event on another day", self.prompt)
        self.assertIn("Reach 3 events by going down the tiers, to tier 3 if needed, still only today", self.prompt)

    def test_mens_only_is_stated_when_set_and_left_out_when_not(self):
        self.assertIn("Men's teams and competitions only", self.prompt)
        self.assertNotIn("Men's teams", preferences.to_prompt({**self.PREFS, "mens_only": False}))

    def test_times_carry_the_time_zone_label(self):
        self.assertIn('Europe/Paris time zone, followed by "CET" (for example 2:45 PM CET)', self.prompt)


if __name__ == "__main__":
    unittest.main()
