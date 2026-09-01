"""Preview ao vivo da captura e das decisoes do detector de setas.

Uso: .\venv\Scripts\python.exe debug_live.py

Controles (com a janela do preview em foco):
  ESPACO  congela o frame e salva original, overlay e mascara
  R       retoma a captura
  S       salva o frame exibido sem alterar pausa
  Q/ESC   encerra
"""
from datetime import datetime
from pathlib import Path
import ctypes
import sys
import time

import cv2
import mss
from pynput.keyboard import Key, Listener

from arrow_detector import analyze_arrow_candidates, is_prompt_screen
from capture import grab_window
from window import get_window_rect


WINDOW_NAME = "DragonMine Z - detector ao vivo"
OUTPUT_DIR = Path("debug_frames")
ACCEPTED_COLOR = (0, 220, 0)
REJECTED_COLOR = (0, 0, 255)
TEXT_COLOR = (255, 255, 255)
WDA_EXCLUDEFROMCAPTURE = 0x00000011


def _enable_dpi_awareness():
    """Alinha coordenadas do OpenCV com as coordenadas fisicas do mss."""
    if sys.platform != "win32":
        return
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def _exclude_preview_from_capture():
    """Impede que o mss recapture as anotacoes do proprio preview."""
    if sys.platform != "win32":
        return False
    hwnd = ctypes.windll.user32.FindWindowW(None, WINDOW_NAME)
    if not hwnd:
        return False
    return bool(ctypes.windll.user32.SetWindowDisplayAffinity(
        hwnd, WDA_EXCLUDEFROMCAPTURE
    ))


def _place_preview_away_from_game(window_rect):
    """Posiciona um preview reduzido ao lado da area capturada, se couber."""
    if sys.platform != "win32":
        return

    left, top, width, height = window_rect
    user32 = ctypes.windll.user32
    virtual_left = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
    virtual_top = user32.GetSystemMetrics(77)    # SM_YVIRTUALSCREEN
    virtual_width = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
    virtual_height = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
    virtual_right = virtual_left + virtual_width
    virtual_bottom = virtual_top + virtual_height

    # Margem extra inclui borda/sombra da janela do HighGUI, que nao faz
    # parte do tamanho passado a resizeWindow.
    gap = 30
    right_space = virtual_right - (left + width + gap)
    left_space = left - virtual_left - gap
    preview_width = min(900, width)

    if right_space >= 320:
        preview_width = min(preview_width, right_space)
        preview_left = left + width + gap
    elif left_space >= 320:
        preview_width = min(preview_width, left_space)
        preview_left = left - gap - preview_width
    else:
        return

    preview_height = max(240, round(height * preview_width / width))
    preview_height = min(preview_height, virtual_height - 80)
    preview_top = min(max(top, virtual_top), virtual_bottom - preview_height - 40)
    cv2.resizeWindow(WINDOW_NAME, preview_width, preview_height)
    cv2.moveWindow(WINDOW_NAME, preview_left, preview_top)


def _put_label(image, text, x, y, color):
    """Desenha texto legivel sem deixar a coordenada sair pelo topo."""
    y = max(16, y)
    cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.43,
                (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.43,
                color, 1, cv2.LINE_AA)


def draw_overlay(frame, analysis, prompt, paused):
    overlay = frame.copy()
    for candidate in analysis["candidates"]:
        x, y, w, h = candidate["rect"]
        color = ACCEPTED_COLOR if candidate["accepted"] else REJECTED_COLOR
        cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)
        direction = candidate["direction"]
        label = direction if candidate["accepted"] else candidate["reason"]
        if direction and not candidate["accepted"]:
            label = f"{direction}: {label}"
        _put_label(overlay, label, x, y - 5, color)

    directions = analysis["directions"]
    status = f"prompt={prompt}  setas={directions or '-'}"
    if paused:
        status = "PAUSADO  " + status
    cv2.rectangle(overlay, (0, 0), (overlay.shape[1], 32), (20, 20, 20), -1)
    _put_label(overlay, status, 10, 22, TEXT_COLOR)
    return overlay


def save_snapshot(frame, overlay, mask):
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    original_path = OUTPUT_DIR / f"{stamp}_original.png"
    overlay_path = OUTPUT_DIR / f"{stamp}_overlay.png"
    mask_path = OUTPUT_DIR / f"{stamp}_mask.png"
    cv2.imwrite(str(original_path), frame)
    cv2.imwrite(str(overlay_path), overlay)
    cv2.imwrite(str(mask_path), mask)
    print(f"Frame salvo em {original_path.parent.resolve()} ({stamp})")


def main():
    print("Procurando a janela com titulo contendo 'DragonMine'...")
    print("F8=pausar+salvar  F9=retomar  F10=salvar (funcionam com o jogo em foco)")
    print("No preview: ESPACO=pausar+salvar  R=retomar  S=salvar  Q/ESC=sair")
    _enable_dpi_awareness()
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    initial_rect = get_window_rect()
    if initial_rect is not None:
        _place_preview_away_from_game(initial_rect)
    preview_excluded = _exclude_preview_from_capture()

    paused = False
    frame = overlay = mask = None
    last_window_warning = 0.0
    pause_and_save_requested = False
    resume_requested = False
    save_requested = False

    def on_global_key(key):
        nonlocal pause_and_save_requested, resume_requested, save_requested
        if key == Key.f8:
            pause_and_save_requested = True
        elif key == Key.f9:
            resume_requested = True
        elif key == Key.f10:
            save_requested = True

    listener = Listener(on_press=on_global_key)
    listener.start()

    try:
        with mss.mss() as sct:
            while True:
                if not paused:
                    window_rect = get_window_rect()
                    if window_rect is None:
                        now = time.time()
                        if now - last_window_warning >= 5:
                            print("Janela do jogo nao encontrada; aguardando...")
                            last_window_warning = now
                    else:
                        frame = grab_window(sct, window_rect)
                        analysis = analyze_arrow_candidates(frame)
                        mask = analysis["mask"]
                        prompt = is_prompt_screen(frame)
                        overlay = draw_overlay(frame, analysis, prompt, paused=False)

                if overlay is not None:
                    shown = overlay.copy()
                    if paused:
                        cv2.rectangle(shown, (0, 0), (shown.shape[1], 32), (20, 20, 20), -1)
                        _put_label(shown, "PAUSADO - R retoma, S salva, Q sai", 10, 22, TEXT_COLOR)
                    cv2.imshow(WINDOW_NAME, shown)

                # Em algumas versoes do HighGUI, o HWND so fica disponivel
                # depois do primeiro imshow/waitKey.
                if not preview_excluded:
                    preview_excluded = _exclude_preview_from_capture()
                    if preview_excluded:
                        print("Preview protegido contra recaptura.")

                key = cv2.waitKey(15) & 0xFF
                if key in (27, ord("q"), ord("Q")):
                    break
                if key == ord(" ") and frame is not None:
                    paused = True
                    save_snapshot(frame, overlay, mask)
                elif key in (ord("r"), ord("R")):
                    paused = False
                elif key in (ord("s"), ord("S")) and frame is not None:
                    save_snapshot(frame, overlay, mask)

                if pause_and_save_requested and frame is not None:
                    pause_and_save_requested = False
                    paused = True
                    save_snapshot(frame, overlay, mask)
                if resume_requested:
                    resume_requested = False
                    paused = False
                if save_requested and frame is not None:
                    save_requested = False
                    save_snapshot(frame, overlay, mask)
    finally:
        listener.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        cv2.destroyAllWindows()
        sys.exit(0)
