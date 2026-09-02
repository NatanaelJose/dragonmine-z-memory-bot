"""
Ferramenta de diagnostico: localiza a janela do jogo, tira um print da
janela inteira, mostra o que o detector de setas enxerga (mascara +
direcoes) e salva os arquivos em disco para voce conferir. Da um tempo
(countdown) antes do print para voce trocar para o jogo e deixar as setas
visiveis na tela ("Memorize!").

Uso: python debug_capture.py
"""
import sys
import time

import cv2
import mss

from arrow_detector import _colored_mask, detect_arrows
from capture import grab_window
from window import get_window_rect

COUNTDOWN_SECONDS = 5


def countdown(seconds):
    for remaining in range(seconds, 0, -1):
        print(f"  Troque para o jogo agora... capturando em {remaining}s", end="\r")
        time.sleep(1)
    print(" " * 70, end="\r")


def main():
    print("Deixe o minigame de memoria com as setas visiveis (fase 'Memorize!').")
    print(f"Voce tem {COUNTDOWN_SECONDS}s apos o ENTER para trocar de janela.")
    input("Pressione ENTER para comecar a contagem...")
    countdown(COUNTDOWN_SECONDS)

    window_rect = get_window_rect()
    if window_rect is None:
        print("Nao encontrei a janela do jogo (titulo contendo 'DragonMine'). Abra o jogo e tente de novo.")
        sys.exit(1)

    with mss.MSS() as sct:
        frame = grab_window(sct, window_rect)

    print("Capturado!")

    cv2.imwrite("debug_window.png", frame)

    mask = _colored_mask(frame)
    cv2.imwrite("debug_window_mask.png", mask)

    directions = detect_arrows(frame)

    print(f"Direcoes detectadas (esq->dir): {directions}")
    print("Arquivos salvos: debug_window.png, debug_window_mask.png")
    print("Confira debug_window_mask.png: apenas as setas devem aparecer brancas, o resto preto.")


if __name__ == "__main__":
    main()
