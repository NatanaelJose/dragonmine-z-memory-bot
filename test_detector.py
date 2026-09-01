"""Teste rapido offline do arrow_detector com simbolos desenhados
sinteticamente, usando o mapeamento real cor->direcao do mod:
verde=down, ciano=left, magenta=right, amarelo=up (cruz)."""
import cv2
import numpy as np

from arrow_detector import detect_arrows, has_bright_text

# BGR das cores reais observadas no jogo
COLOR_BY_DIRECTION = {
    "down": (0, 255, 0),      # verde
    "left": (255, 255, 0),    # ciano
    "right": (255, 0, 255),   # magenta
    "up": (0, 220, 255),      # amarelo (simbolo de cruz)
}


def draw_symbol(canvas, cx, cy, direction, w=40, h=56):
    """Desenha um retangulo solido na cor correspondente a direcao -- a
    forma exata nao importa mais para a deteccao (que agora usa so a cor),
    entao um retangulo simples e suficiente para o teste."""
    color = COLOR_BY_DIRECTION[direction]
    cv2.rectangle(canvas, (cx - w // 2, cy - h // 2), (cx + w // 2, cy + h // 2), color, -1)


def main():
    canvas = np.zeros((120, 500, 3), dtype=np.uint8)
    canvas[:] = (40, 20, 60)  # fundo escuro tipo o jogo

    expected = ["left", "right", "up", "down"]
    for i, direction in enumerate(expected):
        draw_symbol(canvas, 70 + i * 110, 60, direction)

    detected = detect_arrows(canvas)
    print("Esperado :", expected)
    print("Detectado:", detected)
    assert detected == expected, "FALHOU: direcoes nao bateram"
    print("OK: deteccao de direcao (por cor) bateu com o esperado")

    # regiao de titulo simulada: texto claro
    title_on = np.zeros((30, 200, 3), dtype=np.uint8)
    cv2.putText(title_on, "Memorize!", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    title_off = np.zeros((30, 200, 3), dtype=np.uint8)

    print("Texto visivel detectado:", has_bright_text(title_on))
    print("Texto ausente detectado:", not has_bright_text(title_off))
    assert has_bright_text(title_on)
    assert not has_bright_text(title_off)
    print("OK: deteccao de texto do titulo bateu com o esperado")


if __name__ == "__main__":
    main()
