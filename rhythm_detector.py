"""Vision and timing state for DragonMine Z's two-sided rhythm lane."""

from dataclasses import dataclass

import cv2
import numpy as np

from arrow_detector import COLOR_HUE_RANGES, SAT_MIN, VAL_MIN


LEFT_HIT_X = 0.409
RIGHT_HIT_X = 0.591
LANE_Y_MIN = 0.20
LANE_Y_MAX = 0.70


@dataclass(frozen=True)
class RhythmNote:
    direction: str
    side: str
    head_x: float
    tail_x: float
    rect: tuple[int, int, int, int]
    sustained: bool


@dataclass(frozen=True)
class RhythmAction:
    kind: str
    direction: str
    side: str
    sustained: bool = False


def detect_hit_positions(lane_frame):
    """Find the two tall white receptor lines at any Minecraft GUI scale."""
    height, width = lane_frame.shape[:2]
    hsv = cv2.cvtColor(lane_frame, cv2.COLOR_BGR2HSV)
    # O receptor direito pode ser desenhado em cinza (V ~= 140) dependendo
    # do shader e do GUI Scale. Notas continuam saturadas e ficam de fora.
    white = ((hsv[:, :, 1] <= 80) & (hsv[:, :, 2] >= 115)).astype(np.uint8)

    def strongest_vertical_line(start_fraction, end_fraction):
        start = round(width * start_fraction)
        end = round(width * end_fraction)
        scores = np.count_nonzero(white[:, start:end], axis=0)
        minimum = max(8, round(height * 0.30))
        if not len(scores) or int(scores.max()) < minimum:
            return None
        indexes = np.flatnonzero(scores >= minimum)
        groups = np.split(indexes, np.where(np.diff(indexes) > 1)[0] + 1)
        # Cada linha tem poucos pixels de largura. Regioes claras extensas do
        # cenario e da tela anterior nao podem virar um falso receptor.
        groups = [group for group in groups if len(group) <= max(16, round(width * 0.012))]
        if not groups:
            return None
        best = max(groups, key=lambda group: float(scores[group].sum()))
        return start + float(np.mean(best))

    left = strongest_vertical_line(0.28, 0.495)
    right = strongest_vertical_line(0.505, 0.72)
    if left is None or right is None:
        return None
    left_fraction, right_fraction = left / width, right / width
    if abs(left_fraction - (1.0 - right_fraction)) > 0.045:
        return None
    if not 0.08 <= right_fraction - left_fraction <= 0.30:
        return None
    return left_fraction, right_fraction


def _head_and_tail(x, w, h, side):
    """Estimate the head center from the leading edge of the moving note."""
    head_inset = min(w / 2.0, max(4.0, h * 0.42))
    sustained = w > h * 2.2
    if side == "left":
        return x + w - 1 - head_inset, float(x), sustained
    return x + head_inset, float(x + w - 1), sustained


def detect_rhythm_notes(lane_frame):
    """Return colored note heads in a cropped rhythm lane.

    Direction comes from the fixed sprite color. The tall portion of each
    component identifies the head, so a long sustain bar does not move the
    measured hit position away from the arrow itself.
    """
    height, width = lane_frame.shape[:2]
    hsv = cv2.cvtColor(lane_frame, cv2.COLOR_BGR2HSV)
    y_min, y_max = round(height * LANE_Y_MIN), round(height * LANE_Y_MAX)
    kernel_width = max(3, round(height * 0.035)) | 1
    notes = []

    for direction, (hue_low, hue_high) in COLOR_HUE_RANGES.items():
        mask = cv2.inRange(
            hsv,
            np.array([hue_low, SAT_MIN, VAL_MIN]),
            np.array([hue_high, 255, 255]),
        )
        mask[:y_min] = 0
        mask[y_max:] = 0
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            np.ones((3, kernel_width), np.uint8),
        )
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if area < 20:
                continue
            if h < 10 or w < 8:
                continue
            if h > height * 0.42:
                continue

            provisional_side = "left" if x + w / 2 < width / 2 else "right"
            _, _, sustained = _head_and_tail(x, w, h, provisional_side)
            if sustained:
                if x <= width * LEFT_HIT_X:
                    side = "left"
                elif x + w - 1 >= width * RIGHT_HIT_X:
                    side = "right"
                else:
                    side = provisional_side
            else:
                side = provisional_side
            head_x, tail_x, sustained = _head_and_tail(x, w, h, side)
            # Discard scenery near the far edges and colored pixels between
            # the two receptors, where valid incoming heads never originate.
            if side == "left" and not width * 0.03 <= head_x <= width * 0.49:
                continue
            if side == "right" and not width * 0.51 <= head_x <= width * 0.97:
                continue
            notes.append(RhythmNote(direction, side, head_x, tail_x, (x, y, w, h), sustained))

    return sorted(notes, key=lambda note: note.head_x)


class RhythmTracker:
    """Turn note positions into one-shot key actions at each receptor."""

    def __init__(self, lead_seconds=0.008, hit_positions=None):
        self.lead_seconds = lead_seconds
        self.hit_positions = hit_positions or (LEFT_HIT_X, RIGHT_HIT_X)
        self.states = {}

    def _target(self, side, width):
        index = 0 if side == "left" else 1
        return width * self.hit_positions[index]

    def update(self, notes, width, now):
        actions = []
        grouped = {}
        for note in notes:
            grouped.setdefault((note.side, note.direction), []).append(note)

        all_keys = set(self.states) | set(grouped)
        for key in all_keys:
            side, direction = key
            target = self._target(side, width)
            state = self.states.setdefault(key, {
                "last_head": None,
                "last_time": None,
                "latched": False,
                "held": False,
                "missing": 0,
            })
            candidates = grouped.get(key, [])
            if state["held"] and candidates:
                # A sustain head keeps travelling well past the receptor.
                # Continue following that same component until its trailing
                # edge reaches the line instead of dropping it after 3 frames.
                last_head = state["last_head"]
                candidate = min(
                    candidates,
                    key=lambda note: abs(note.head_x - last_head) if last_head is not None else 0,
                )
            elif side == "left":
                candidates = [note for note in candidates if note.head_x <= target + width * 0.035]
                candidate = max(candidates, key=lambda note: note.head_x, default=None)
            else:
                candidates = [note for note in candidates if note.head_x >= target - width * 0.035]
                candidate = min(candidates, key=lambda note: note.head_x, default=None)
            if candidate is None:
                state["missing"] += 1
                if state["held"] and state["missing"] >= 2:
                    actions.append(RhythmAction("release", direction, side, True))
                    state["held"] = False
                if state["missing"] >= 3:
                    state["latched"] = False
                    state["last_head"] = None
                    state["last_time"] = None
                continue

            state["missing"] = 0
            head = candidate.head_x
            tolerance = max(3.0, width * 0.002)
            previous = state["last_head"]
            previous_time = state["last_time"]
            crossed = previous is not None and (
                (side == "left" and previous < target <= head)
                or (side == "right" and previous > target >= head)
            )
            imminent = False
            if previous is not None and previous_time is not None and now > previous_time:
                velocity = (head - previous) / (now - previous_time)
                distance = target - head
                approaching = velocity > 20 if side == "left" else velocity < -20
                eta = distance / velocity if approaching else float("inf")
                imminent = abs(head - target) <= tolerance or 0 <= eta <= self.lead_seconds

            if not state["latched"] and (crossed or imminent):
                actions.append(RhythmAction("press", direction, side, candidate.sustained))
                state["latched"] = True
                state["held"] = candidate.sustained

            if state["held"]:
                tail_crossed = (
                    side == "left" and candidate.tail_x >= target - tolerance
                ) or (
                    side == "right" and candidate.tail_x <= target + tolerance
                )
                if tail_crossed:
                    actions.append(RhythmAction("release", direction, side, True))
                    state["held"] = False

            passed = (
                side == "left" and head > target + width * 0.025
            ) or (
                side == "right" and head < target - width * 0.025
            )
            if passed and not state["held"]:
                state["latched"] = False

            state["last_head"] = head
            state["last_time"] = now

        return actions
