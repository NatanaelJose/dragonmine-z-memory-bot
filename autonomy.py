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


def find_minigame_menu_panels(frame):
    """Return the left/right green menu panels at any Minecraft GUI scale."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, MENU_GREEN_LOWER, MENU_GREEN_UPPER)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    height, width = mask.shape
    boxes = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        if (
            box_width < width * 0.07
            or box_height < height * 0.28
            or box_width > width * 0.42
            or box_height > height * 0.92
            or box_height / max(box_width, 1) < 1.15
        ):
            continue
        roi = mask[y:y + box_height, x:x + box_width]
        density = float(np.count_nonzero(roi)) / roi.size
        if density >= 0.18:
            boxes.append((x, y, box_width, box_height))

    left = [box for box in boxes if box[0] + box[2] / 2 < width / 2]
    right = [box for box in boxes if box[0] + box[2] / 2 > width / 2]
    if not left or not right:
        return None
    left_box = max(left, key=lambda box: box[2] * box[3])
    right_box = max(right, key=lambda box: box[2] * box[3])
    height_ratio = left_box[3] / right_box[3]
    if not 0.65 <= height_ratio <= 1.55:
        return None
    if abs(left_box[1] - right_box[1]) > height * 0.18:
        return None
    return left_box, right_box


def is_minigame_menu(frame):
    """Recognize the two tall green panels without reading localized text."""
    return find_minigame_menu_panels(frame) is not None


def menu_click_points(window_rect, game, frame=None):
    """Return absolute menu clicks, using detected panels when available."""
    left, top, width, height = window_rect

    if frame is not None:
        panels = find_minigame_menu_panels(frame)
        if panels is not None:
            left_panel, right_panel = panels
            item_fraction_y = 0.19 if game == "rhythm" else 0.38
            item = (
                left + round(left_panel[0] + left_panel[2] * 0.18),
                top + round(left_panel[1] + left_panel[3] * item_fraction_y),
            )
            play = (
                left + round(right_panel[0] + right_panel[2] * 0.57),
                top + round(right_panel[1] + right_panel[3] * 0.93),
            )
            return item, play

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
    menu_rect, menu_frame = _wait_for_frame(sct, is_minigame_menu, timeout=1.2)
    if menu_rect is None:
        log("AUTONOMY:START Prompt inicial liberado; menu nao apareceu.")
        return False

    log(f"AUTONOMY:MENU Menu detectado; selecionando {game}.")
    focus_game_window()
    item_point, play_point = menu_click_points(menu_rect, game, menu_frame)
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
        current_frame = grab_window(sct, current_rect)
        focus_game_window()
        item_point, play_point = menu_click_points(current_rect, game, current_frame)
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
