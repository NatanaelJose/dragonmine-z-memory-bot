"""Escape-aware input interruption shared by both autoplay modes."""

import threading

from pynput.keyboard import Key, Listener


class EscapeInterruptGuard:
    """Cancel current bot input once per physical Escape press."""

    def __init__(self, log, start_listener=True):
        self.log = log
        self._interrupt_requested = threading.Event()
        self._state_lock = threading.Lock()
        self._escape_down = False
        self._listener = Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) if start_listener else None

    @property
    def interrupt_requested(self):
        return self._interrupt_requested.is_set()

    def _on_press(self, key):
        if key != Key.esc:
            return
        with self._state_lock:
            if self._escape_down:
                return
            self._escape_down = True
            self._interrupt_requested.set()
            self.log("INPUT:INTERRUPT_REQUESTED Esc detectado; cancelando entradas atuais.")

    def _on_release(self, key):
        if key == Key.esc:
            with self._state_lock:
                self._escape_down = False

    def start(self):
        if self._listener is not None:
            self._listener.start()
        return self

    def consume_if_requested(self, release_inputs):
        """Release held controls and consume one pending interruption."""
        if not self._interrupt_requested.is_set():
            return False
        self._interrupt_requested.clear()
        release_inputs()
        return True

    def stop(self):
        if self._listener is not None:
            self._listener.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
