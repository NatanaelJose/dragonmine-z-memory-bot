import unittest

from pynput.keyboard import Key

from input_pause import EscapePauseGuard


class EscapePauseGuardTests(unittest.TestCase):
    def test_escape_toggles_only_once_per_physical_press(self):
        logs = []
        guard = EscapePauseGuard(logs.append, start_listener=False)

        guard._on_press(Key.esc)
        guard._on_press(Key.esc)
        self.assertTrue(guard.paused)
        self.assertEqual(len(logs), 1)

        guard._on_release(Key.esc)
        guard._on_press(Key.esc)
        self.assertFalse(guard.paused)
        self.assertEqual(len(logs), 2)


if __name__ == "__main__":
    unittest.main()
