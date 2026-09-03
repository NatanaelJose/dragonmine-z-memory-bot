"""User-controlled input suspension shared by both autoplay modes."""

import threading
import time

from pynput.keyboard import Key, Listener


class EscapePauseGuard:
    """Toggle bot input on physical Escape presses without losing progress."""

    def __init__(self, log, start_listener=True):
        self.log = log
        self._paused = threading.Event()
        self._state_lock = threading.Lock()
        self._escape_down = False
        self._listener = Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) if start_listener else None

    @property
    def paused(self):
        return self._paused.is_set()

    def _on_press(self, key):
        if key != Key.esc:
            return
        with self._state_lock:
            if self._escape_down:
                return
            self._escape_down = True
            if self._paused.is_set():
                self._paused.clear()
                self.log("INPUT:RESUMED Esc detectado novamente; retomando o bot.")
            else:
                self._paused.set()
                self.log("INPUT:PAUSED Esc detectado; pressione Esc novamente para retomar.")

    def _on_release(self, key):
        if key == Key.esc:
            with self._state_lock:
                self._escape_down = False

    def start(self):
        if self._listener is not None:
            self._listener.start()
        return self

    def wait_if_paused(self, release_inputs):
        """Release held controls and block until the user presses Escape again."""
        if not self._paused.is_set():
            return False
        release_inputs()
        waited = True
        while self._paused.is_set():
            time.sleep(0.03)
        return waited

    def stop(self):
        if self._listener is not None:
            self._listener.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
