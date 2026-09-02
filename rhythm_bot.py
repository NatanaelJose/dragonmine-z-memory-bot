"""Real-time autoplay for DragonMine Z's rhythm minigame."""

import time

import mss
from pynput.keyboard import Controller, Key

from arrow_detector import is_prompt_screen
from autonomy import handle_prompt
from capture import grab_window
from rhythm_capture import lane_capture_rect
from rhythm_detector import RhythmTracker, detect_rhythm_notes
from window import focus_game_window, get_window_rect


KEYS = {
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
}
SYMBOLS = {"up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT"}
TAP_SECONDS = 0.030
MAX_HOLD_SECONDS = 3.0


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


class RhythmKeyboard:
    def __init__(self):
        self.keyboard = Controller()
        self.active = {}

    def press(self, action, now):
        source = (action.side, action.direction)
        if source in self.active:
            return
        if not any(direction == action.direction for direction, _, _ in self.active.values()):
            self.keyboard.press(KEYS[action.direction])
        deadline = None if action.sustained else now + TAP_SECONDS
        self.active[source] = (action.direction, deadline, now)

    def release(self, action):
        self._release_source((action.side, action.direction))

    def _release_source(self, source):
        entry = self.active.pop(source, None)
        if entry is None:
            return
        direction = entry[0]
        if not any(value[0] == direction for value in self.active.values()):
            self.keyboard.release(KEYS[direction])

    def tick(self, now):
        for source, (_, deadline, started_at) in list(self.active.items()):
            if (deadline is not None and now >= deadline) or now - started_at >= MAX_HOLD_SECONDS:
                self._release_source(source)

    def release_all(self):
        for source in list(self.active):
            self._release_source(source)
        # Defensive key-up events also clear a key if the process was stopped
        # between Controller.press and registration in the active map.
        for key in KEYS.values():
            self.keyboard.release(key)


def _wait_for_window():
    last_warning = 0.0
    while True:
        rect = get_window_rect()
        if rect is not None:
            return rect
        now = time.time()
        if now - last_warning >= 3:
            log("RHYTHM:WAITING Abra a janela DragonMine.")
            last_warning = now
        time.sleep(0.25)


def run_rhythm(lead_ms=8.0, verbose=False, autonomous=False):
    """Watch the lane and send arrow key down/up events at both receptors."""
    window_rect = _wait_for_window()
    focus_game_window()
    time.sleep(0.25)
    tracker = RhythmTracker(lead_seconds=lead_ms / 1000.0)
    inputs = RhythmKeyboard()
    frame_count = 0
    status_started = time.perf_counter()
    last_rect_check = status_started
    last_autonomy_check = status_started

    def press_any_key():
        inputs.keyboard.press(Key.space)
        time.sleep(TAP_SECONDS)
        inputs.keyboard.release(Key.space)

    log(f"RHYTHM:READY Detector ativo com antecipacao de {lead_ms:.0f} ms.")
    try:
        with mss.MSS() as sct:
            full_frame = grab_window(sct, window_rect)
            if is_prompt_screen(full_frame):
                log("RHYTHM:START Tela inicial detectada; iniciando a musica.")
                handle_prompt(
                    sct,
                    window_rect,
                    "rhythm",
                    press_any_key,
                    autonomous,
                    log,
                )

            lane_rect = lane_capture_rect(window_rect)
            log("RHYTHM:TRACKING Acompanhando notas nas duas pistas.")
            while True:
                now = time.perf_counter()
                if now - last_rect_check >= 1.0:
                    current_rect = get_window_rect()
                    if current_rect is None:
                        inputs.release_all()
                        log("RHYTHM:WAITING Janela perdida; aguardando retorno.")
                        window_rect = _wait_for_window()
                        focus_game_window()
                    else:
                        window_rect = current_rect
                    lane_rect = lane_capture_rect(window_rect)
                    last_rect_check = now

                if autonomous and now - last_autonomy_check >= 0.5:
                    full_frame = grab_window(sct, window_rect)
                    last_autonomy_check = now
                    if is_prompt_screen(full_frame):
                        inputs.release_all()
                        log("AUTONOMY:FAIL Tela final detectada no ritmo.")
                        handle_prompt(
                            sct,
                            window_rect,
                            "rhythm",
                            press_any_key,
                            True,
                            log,
                        )
                        tracker = RhythmTracker(lead_seconds=lead_ms / 1000.0)
                        window_rect = get_window_rect() or window_rect
                        lane_rect = lane_capture_rect(window_rect)
                        last_rect_check = time.perf_counter()
                        last_autonomy_check = last_rect_check
                        continue

                lane = grab_window(sct, lane_rect)
                notes = detect_rhythm_notes(lane)
                actions = tracker.update(notes, lane.shape[1], now)
                for action in actions:
                    if action.kind == "press":
                        inputs.press(action, now)
                        event = "HOLD_START" if action.sustained else "HIT"
                        log(f"RHYTHM:{event} {SYMBOLS[action.direction]} via {action.side}.")
                    else:
                        inputs.release(action)
                        log(f"RHYTHM:HOLD_END {SYMBOLS[action.direction]} via {action.side}.")
                inputs.tick(now)
                frame_count += 1

                elapsed = now - status_started
                if elapsed >= 2.0:
                    if verbose:
                        log(f"RHYTHM:FPS {frame_count / elapsed:.1f} FPS; {len(notes)} candidatos.")
                    frame_count = 0
                    status_started = now
                time.sleep(0.001)
    finally:
        inputs.release_all()
