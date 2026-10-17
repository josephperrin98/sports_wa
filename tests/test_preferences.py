import unittest

from app import preferences


class LoadTest(unittest.TestCase):
    def test_the_real_preferences_file_loads_and_renders(self):
        prompt = preferences.to_prompt(preferences.load())

        self.assertIn("Serie A (tier 3): search Italian broadcasters, in Italian.", prompt)


class ToPromptTest(unittest.TestCase):
    def test_renders_competitions_rules_and_limits(self):
        prefs = {
            "timezone": "Europe/Paris",
            "starting_soon_hours": 3,
            "min_events": 3,
            "max_events": 5,
            "max_per_sport": 2,
            "language_rules": ["Rule one.", "Rule two."],
            "competitions": [{"name": "Ligue 1", "tier": 1, "language": "French"}],
        }

        prompt = preferences.to_prompt(prefs)

        self.assertIn("- Ligue 1 (tier 1): search French broadcasters, in French.", prompt)
        self.assertIn("1. Rule one.\n2. Rule two.", prompt)
        self.assertIn("3 to 5 events, at most 2 from the same sport", prompt)
        self.assertIn("within 3 hours", prompt)
        self.assertIn("Europe/Paris", prompt)


if __name__ == "__main__":
    unittest.main()
