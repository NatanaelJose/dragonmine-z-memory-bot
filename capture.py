"""Screen capture helpers shared by the bot and diagnostic tools."""

import cv2
import mss
import numpy as np


def grab_window(sct: mss.mss, window_rect):
    """Capture a Windows client-area rectangle and return a BGR frame."""
    left, top, width, height = window_rect
    shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
    image = np.array(shot)  # MSS returns BGRA.
    return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
