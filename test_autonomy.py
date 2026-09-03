import unittest
from unittest.mock import patch

import cv2
import numpy as np

from autonomy import (
    _dismiss_new_game_prompt,
    find_minigame_menu_panels,
    is_minigame_menu,
    menu_click_points,
)


class AutonomyTests(unittest.TestCase):
    def test_detects_two_panel_minigame_menu(self):
        frame = np.zeros((480, 854, 3), dtype=np.uint8)
        green = cv2.cvtColor(np.uint8([[[60, 220, 85]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
        cv2.rectangle(frame, (27, 30), (300, 451), green, -1)
        cv2.rectangle(frame, (538, 30), (814, 451), green, -1)
        self.assertTrue(is_minigame_menu(frame))

    def test_rejects_single_green_result_panel(self):
        frame = np.zeros((480, 854, 3), dtype=np.uint8)
        green = cv2.cvtColor(np.uint8([[[60, 220, 85]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
        cv2.rectangle(frame, (118, 121), (732, 357), green, -1)
        self.assertFalse(is_minigame_menu(frame))

    def test_click_points_follow_window_position_and_size(self):
        item, play = menu_click_points((100, 200, 854, 480), "memory")
        self.assertEqual(item, (228, 392))
        self.assertEqual(play, (796, 620))

    def test_smaller_gui_scale_uses_detected_panel_geometry(self):
        frame = np.zeros((480, 854, 3), dtype=np.uint8)
        green = cv2.cvtColor(np.uint8([[[60, 220, 85]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
        cv2.rectangle(frame, (140, 120), (280, 390), green, -1)
        cv2.rectangle(frame, (574, 120), (714, 390), green, -1)

        self.assertEqual(
            find_minigame_menu_panels(frame),
            ((140, 120, 141, 271), (574, 120, 141, 271)),
        )
        item, play = menu_click_points((100, 200, 854, 480), "memory", frame)
        self.assertEqual(item, (265, 423))
        self.assertEqual(play, (754, 572))

    def test_rhythm_click_tracks_scaled_left_panel(self):
        frame = np.zeros((480, 854, 3), dtype=np.uint8)
        green = cv2.cvtColor(np.uint8([[[60, 220, 85]]]), cv2.COLOR_HSV2BGR)[0, 0].tolist()
        cv2.rectangle(frame, (140, 120), (280, 390), green, -1)
        cv2.rectangle(frame, (574, 120), (714, 390), green, -1)

        item, _ = menu_click_points((0, 0, 854, 480), "rhythm", frame)
        self.assertEqual(item, (165, 171))

    @patch("autonomy.time.sleep")
    @patch("autonomy.focus_game_window")
    @patch("autonomy._wait_for_frame")
    def test_start_prompt_retries_until_it_is_visibly_closed(
        self,
        wait_for_frame,
        _focus_game_window,
        _sleep,
    ):
        wait_for_frame.side_effect = [(None, None), ((0, 0, 854, 480), object())]
        presses = []
        logs = []

        confirmed = _dismiss_new_game_prompt(
            object(),
            (0, 0, 854, 480),
            lambda: presses.append(True),
            logs.append,
        )

        self.assertTrue(confirmed)
        self.assertEqual(len(presses), 2)
        self.assertTrue(any("START_RETRY" in line for line in logs))
        self.assertTrue(any("START_CONFIRMED" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
