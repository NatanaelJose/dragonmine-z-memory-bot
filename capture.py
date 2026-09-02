"""Screen capture helpers shared by the bot and diagnostic tools."""

import math

import cv2
import mss
import numpy as np


MEMORY_REGION = {
    "left": 0.10,
    "top": 0.25,
    "right": 0.90,
    "bottom": 0.82,
}


def grab_window(sct: mss.MSS, window_rect):
    """Capture a Windows client-area rectangle and return a BGR frame."""
    left, top, width, height = window_rect
    shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
    image = np.array(shot)  # MSS returns BGRA.
    return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)


def normalized_capture_rect(window_rect, region):
    """Convert a normalized client-area region into an absolute MSS rect."""
    window_left, window_top, width, height = window_rect
    left = max(0, min(width - 1, round(width * region["left"])))
    top = max(0, min(height - 1, round(height * region["top"])))
    right = max(left + 1, min(width, round(width * region["right"])))
    bottom = max(top + 1, min(height, round(height * region["bottom"])))
    return window_left + left, window_top + top, right - left, bottom - top


def memory_capture_rect(window_rect, expected_arrows=None):
    """Return a fast region that expands when the sequence wraps downward."""
    region = dict(MEMORY_REGION)
    if expected_arrows is not None:
        rows = math.ceil(expected_arrows / 13)
        extra_rows = max(0, rows - 4)
        # Expand just enough to include the new top row. Expanding too far
        # upward admits the green score text, which can split the arrow grid.
        region["top"] = max(0.05, region["top"] - extra_rows * 0.04)
        region["bottom"] = min(0.95, region["bottom"] + extra_rows * 0.06)
    return normalized_capture_rect(window_rect, region)
