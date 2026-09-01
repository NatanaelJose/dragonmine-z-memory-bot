import cv2
import numpy as np
import unittest

from rhythm_detector import RhythmNote, RhythmTracker, detect_rhythm_notes


COLORS = {
    "left": (255, 255, 0),
    "down": (0, 255, 0),
    "up": (0, 255, 255),
    "right": (255, 0, 255),
}


def make_note(direction, head_x, side="left", sustain=0):
    frame = np.zeros((253, 1766, 3), dtype=np.uint8)
    color = COLORS[direction]
    cv2.rectangle(frame, (head_x - 16, 82), (head_x + 16, 124), color, -1)
    if sustain:
        if side == "left":
            cv2.rectangle(frame, (head_x - sustain, 96), (head_x - 17, 110), color, -1)
        else:
            cv2.rectangle(frame, (head_x + 17, 96), (head_x + sustain, 110), color, -1)
    return frame


class RhythmDetectorTests(unittest.TestCase):
    def test_detects_tap_direction_and_head(self):
        notes = detect_rhythm_notes(make_note("up", 600))
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].direction, "up")
        self.assertEqual(notes[0].side, "left")
        self.assertLessEqual(abs(notes[0].head_x - 600), 2)
        self.assertFalse(notes[0].sustained)

    def test_sustain_trail_does_not_shift_head(self):
        notes = detect_rhythm_notes(make_note("down", 700, sustain=250))
        self.assertEqual(len(notes), 1)
        self.assertLessEqual(abs(notes[0].head_x - 700), 3)
        self.assertLess(notes[0].tail_x, 460)
        self.assertTrue(notes[0].sustained)

    def test_tracker_presses_once_when_note_crosses(self):
        tracker = RhythmTracker(lead_seconds=0)
        actions = []
        for index, x in enumerate((690, 710, 724, 738, 755)):
            note = detect_rhythm_notes(make_note("left", x))[0]
            actions.extend(tracker.update([note], 1766, index / 60))
        presses = [action for action in actions if action.kind == "press"]
        self.assertEqual(len(presses), 1)
        self.assertEqual(presses[0].direction, "left")

    def test_tracker_keeps_sustain_held_after_head_passes_receptor(self):
        tracker = RhythmTracker(lead_seconds=0)
        make = lambda head, tail: RhythmNote("up", "left", head, tail, (0, 0, 300, 40), True)
        tracker.update([make(690, 300)], 1766, 0.00)
        actions = tracker.update([make(730, 340)], 1766, 0.02)
        self.assertEqual([action.kind for action in actions], ["press"])
        actions = tracker.update([make(820, 430)], 1766, 0.04)
        self.assertEqual(actions, [])
        actions = tracker.update([make(1100, 724)], 1766, 0.20)
        self.assertEqual([action.kind for action in actions], ["release"])


if __name__ == "__main__":
    unittest.main()
