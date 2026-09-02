"""Autonomous return-to-menu navigation for DragonMine Z minigames."""

import time

import cv2
import numpy as np
from pynput.mouse import Button, Controller as MouseController

from arrow_detector import is_prompt_screen
from capture import grab_window
from window import focus_game_window, get_window_rect


MENU_GREEN_LOWER = np.array([45, 55, 25])
MENU_GREEN_UPPER = np.array([80, 255, 175])

# Normalized client-area coordinates measured from the minigame menu. The
# order is stable, so navigation does not depend on Portuguese UI text.
MENU_ITEM_POINTS = {
    "rhythm": (0.15, 0.23),
    "memory": (0.15, 0.40),
}
PLAY_POINT = (0.815, 0.875)


def _region_fraction(mask, bounds):
    height, width = mask.shape
    left, top, right, bottom = bounds
    roi = mask[
        round(height * top):round(height * bottom),
        round(width * left):round(width * right),
    ]
    return float(np.count_nonzero(roi)) / roi.size if roi.size else 0.0


def is_minigame_menu(frame):
    """Recognize the two tall green panels without reading localized text."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, MENU_GREEN_LOWER, MENU_GREEN_UPPER)
    left_density = _region_fraction(mask, (0.045, 0.10, 0.335, 0.90))
    right_density = _region_fraction(mask, (0.645, 0.10, 0.94, 0.90))
    center_density = _region_fraction(mask, (0.40, 0.12, 0.60, 0.88))
    return (
        left_density >= 0.20
        and right_density >= 0.20
        and left_density - center_density >= 0.10
        and right_density - center_density >= 0.10
    )


def menu_click_points(window_rect, game):
    """Return absolute screen points for the menu item and Play button."""
    left, top, width, height = window_rect

    def absolute(point):
        return (
            left + round(width * point[0]),
            top + round(height * point[1]),
        )

    return absolute(MENU_ITEM_POINTS[game]), absolute(PLAY_POINT)


def _click(point, mouse):
    mouse.position = point
    time.sleep(0.08)
    mouse.click(Button.left, 1)


def _wait_for_frame(sct, predicate, timeout, interval=0.08):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        window_rect = get_window_rect()
        if window_rect is None:
            return None, None
        frame = grab_window(sct, window_rect)
        if predicate(frame):
            return window_rect, frame
        time.sleep(interval)
    return None, None


def handle_prompt(sct, window_rect, game, press_any_key, autonomous, log):
    """Dismiss a prompt and, when enabled, restart from the minigame menu.

    Returns True only when the menu was found and Play was clicked. A normal
    pre-game prompt is still dismissed, but is not mistaken for a failure.
    """
    focus_game_window()
    time.sleep(0.18)
    press_any_key()
    if not autonomous:
        _wait_for_frame(sct, lambda frame: not is_prompt_screen(frame), timeout=1.2)
        return False

    # Failure prompts lead to the two-panel menu. A normal start prompt leads
    # straight into gameplay, so only navigate after positively seeing it.
    menu_rect, _ = _wait_for_frame(sct, is_minigame_menu, timeout=1.2)
    if menu_rect is None:
        log("AUTONOMY:START Prompt inicial liberado; menu nao apareceu.")
        return False

    log(f"AUTONOMY:MENU Menu detectado; selecionando {game}.")
    focus_game_window()
    item_point, play_point = menu_click_points(menu_rect, game)
    mouse = MouseController()
    _click(item_point, mouse)
    time.sleep(0.22)
    _click(play_point, mouse)
    log("AUTONOMY:PLAY Jogar acionado; aguardando o minigame.")

    # A click is not success by itself. Confirm that both menu panels left
    # the screen; otherwise retry the explicit item + Play clicks once.
    game_rect, _ = _wait_for_frame(
        sct,
        lambda frame: not is_minigame_menu(frame),
        timeout=0.9,
    )
    if game_rect is None:
        log("AUTONOMY:PLAY_RETRY Menu ainda visivel; repetindo os cliques.")
        current_rect = get_window_rect() or menu_rect
        focus_game_window()
        item_point, play_point = menu_click_points(current_rect, game)
        _click(item_point, mouse)
        time.sleep(0.22)
        _click(play_point, mouse)
        game_rect, _ = _wait_for_frame(
            sct,
            lambda frame: not is_minigame_menu(frame),
            timeout=1.2,
        )
    if game_rect is None:
        log("AUTONOMY:PLAY_FAILED Menu continuou aberto; reinicio cancelado.")
        return False
    log("AUTONOMY:PLAY_CONFIRMED Menu fechado; minigame aberto.")

    # Some versions open directly; others show one more any-key prompt.
    prompt_rect, _ = _wait_for_frame(sct, is_prompt_screen, timeout=0.8)
    if prompt_rect is not None:
        focus_game_window()
        time.sleep(0.12)
        press_any_key()
        log("AUTONOMY:START Prompt do novo jogo liberado.")
    return True
