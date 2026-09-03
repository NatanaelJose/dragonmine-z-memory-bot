import unittest
from unittest.mock import patch

from pynput.keyboard import Key

from input_pause import EscapeInterruptGuard
import main


class EscapeInterruptGuardTests(unittest.TestCase):
    def test_escape_requests_one_interrupt_and_releases(self):
        logs = []
        guard = EscapeInterruptGuard(logs.append, start_listener=False)

        guard._on_press(Key.esc)
        guard._on_press(Key.esc)
        self.assertTrue(guard.interrupt_requested)
        self.assertEqual(len(logs), 1)

        releases = []
        self.assertTrue(guard.consume_if_requested(lambda: releases.append(True)))
        self.assertEqual(releases, [True])
        self.assertFalse(guard.interrupt_requested)
        self.assertFalse(guard.consume_if_requested(lambda: releases.append(True)))

    def test_stopped_guard_prevents_the_next_sequence_key(self):
        guard = EscapeInterruptGuard(lambda _message: None, start_listener=False)
        guard._on_press(Key.esc)

        with patch.object(main, "release_gameplay_keys") as release_keys:
            with patch.object(main.keyboard, "press") as press_key:
                sent = main.press_sequence(["left", "right"], interrupt_guard=guard)

        release_keys.assert_called_once()
        press_key.assert_not_called()
        self.assertFalse(sent)


if __name__ == "__main__":
    unittest.main()
