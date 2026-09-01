"""Localiza a janela do Minecraft (mod DragonMine Z) automaticamente pelo
titulo, para nao depender de coordenadas fixas de tela."""
import ctypes
from ctypes import wintypes

import pygetwindow as gw

# Trecho que aparece no titulo da janela em qualquer versao/mundo, ex:
# "DragonMine Z - End of Z v2.1.3 | Multiplayer (Hosted World)"
WINDOW_TITLE_HINT = "DragonMine"


def find_game_window(title_hint=WINDOW_TITLE_HINT):
    """Retorna o objeto de janela (pygetwindow) cujo titulo contem
    title_hint, ou None se nao encontrar."""
    for window in gw.getAllWindows():
        if title_hint.lower() in window.title.lower():
            return window
    return None


def _get_client_rect_screen_coords(hwnd):
    """Retorna (left, top, width, height) da AREA DE CONTEUDO da janela
    (sem a barra de titulo e bordas), em coordenadas de tela. Usa a API do
    Windows diretamente porque pygetwindow so da o retangulo da janela
    inteira, que inclui a barra de titulo -- isso fazia a captura pegar
    pixels brancos da barra de titulo do Windows junto com o jogo, gerando
    um unico blob gigante que quebrava a deteccao de setas."""
    rect = wintypes.RECT()
    if not ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect)):
        return None
    point = wintypes.POINT(0, 0)
    if not ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(point)):
        return None
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return None
    return (point.x, point.y, width, height)


def get_window_rect(title_hint=WINDOW_TITLE_HINT):
    """Retorna (left, top, width, height) da AREA DE CONTEUDO da janela do
    jogo (sem barra de titulo/bordas), ou None se nao encontrar."""
    window = find_game_window(title_hint)
    if window is None:
        return None
    client_rect = _get_client_rect_screen_coords(window._hWnd)
    if client_rect is not None:
        return client_rect
    # fallback: retangulo da janela inteira (inclui barra de titulo)
    if window.width <= 0 or window.height <= 0:
        return None
    return (window.left, window.top, window.width, window.height)


def focus_game_window(title_hint=WINDOW_TITLE_HINT):
    """Traz a janela do jogo para frente e da foco a ela. Retorna True se
    conseguiu, False se nao achou a janela."""
    window = find_game_window(title_hint)
    if window is None:
        return False
    try:
        if window.isMinimized:
            window.restore()
        window.activate()
    except Exception:
        pass
    return True
