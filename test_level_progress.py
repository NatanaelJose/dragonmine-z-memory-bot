import unittest
from unittest.mock import patch

from level_progress import (
    LevelProgress,
    expected_arrows_for_level,
    sequence_limit_for_target,
    wrong_direction_for,
)
from main import submit_forced_failure


class LevelProgressTests(unittest.TestCase):
    def test_expected_arrow_progression_matches_observed_levels(self):
        self.assertEqual(expected_arrows_for_level(1), 3)
        self.assertEqual(expected_arrows_for_level(13), 9)
        self.assertEqual(expected_arrows_for_level(61), 33)
        self.assertEqual(expected_arrows_for_level(145), 75)

    def test_arrow_capacity_tracks_target_and_confirmation_round(self):
        self.assertEqual(sequence_limit_for_target(None), 128)
        self.assertEqual(sequence_limit_for_target(61), 35)
        self.assertEqual(sequence_limit_for_target(999), 504)

    def test_forced_reset_direction_is_always_wrong(self):
        for expected in ("up", "down", "left", "right"):
            self.assertNotEqual(wrong_direction_for(expected), expected)

    @patch("main.press_sequence")
    def test_runtime_forced_reset_sends_only_one_wrong_key(self, press_sequence):
        sent = submit_forced_failure(["up", "left", "right"], 0.03, 0.03)

        self.assertEqual(sent, "down")
        press_sequence.assert_called_once_with(["down"], 0.03, 0.03)

    def test_counts_only_when_next_round_appears(self):
        progress = LevelProgress(2)

        first = progress.begin_round()
        self.assertEqual(first.current_level, 1)
        self.assertIsNone(first.completed_level)
        self.assertEqual(progress.best_completed, 0)

        second = progress.begin_round()
        self.assertEqual(second.current_level, 2)
        self.assertEqual(second.completed_level, 1)
        self.assertFalse(second.target_reached)

        reached = progress.begin_round()
        self.assertEqual(reached.completed_level, 2)
        self.assertTrue(reached.target_reached)
        self.assertEqual(progress.best_completed, 2)

    def test_retry_resets_run_but_preserves_record(self):
        progress = LevelProgress()
        progress.begin_round()
        progress.begin_round()
        progress.begin_round()
        self.assertEqual(progress.best_completed, 2)

        progress.reset_run()
        retry = progress.begin_round()
        self.assertEqual(retry.current_level, 1)
        self.assertEqual(progress.best_completed, 2)

    def test_record_does_not_complete_target_in_a_fresh_run(self):
        progress = LevelProgress(2)
        progress.begin_round()
        progress.begin_round()
        self.assertTrue(progress.begin_round().target_reached)

        progress.reset_run()
        retry = progress.begin_round()
        self.assertEqual(retry.current_level, 1)
        self.assertFalse(retry.target_reached)
        self.assertEqual(progress.best_completed, 2)


if __name__ == "__main__":
    unittest.main()
