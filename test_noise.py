"""Teste: garante que ruido colorido espalhado pela janela (HUD, blocos)
nao e confundido com setas do minigame -- importante desde que o bot passou
a escanear a janela inteira, sem regiao calibrada."""
import cv2
import numpy as np

from arrow_detector import detect_arrows
from test_detector import draw_symbol


def main():
    canvas = np.zeros((600, 900, 3), dtype=np.uint8)
    canvas[:] = (40, 20, 60)

    # ruido: blobs coloridos espalhados pela tela (simulando HUD/itens),
    # longe da linha das setas e de tamanhos variados
    rng = np.random.default_rng(42)
    for _ in range(15):
        x, y = rng.integers(0, 850), rng.integers(0, 580)
        w, h = rng.integers(5, 15), rng.integers(5, 15)
        color = tuple(int(c) for c in rng.integers(150, 255, size=3))
        cv2.rectangle(canvas, (x, y), (x + w, y + h), color, -1)

    # as 3 setas de verdade, no meio da tela
    expected = ["left", "right", "down"]
    for i, direction in enumerate(expected):
        draw_symbol(canvas, 400 + i * 110, 300, direction)

    detected = detect_arrows(canvas)
    print("Esperado :", expected)
    print("Detectado:", detected)
    assert detected == expected, "FALHOU: ruido atrapalhou a deteccao"
    print("OK: ruido de fundo nao atrapalhou a deteccao")

    # Regressao de uma captura real: o titulo amarelo "Boxe Sombrio"
    # formava 10 blobs grandes na mesma linha e vencia as 3 setas menores.
    # As setas magenta/ciano tinham apenas 20px de altura nessa resolucao.
    canvas2 = np.zeros((460, 1100, 3), dtype=np.uint8)
    canvas2[:] = (40, 20, 60)
    for i in range(10):
        draw_symbol(canvas2, 330 + i * 45, 50, "up", w=36, h=30)

    expected2 = ["down", "right", "left"]
    draw_symbol(canvas2, 490, 312, "down", w=20, h=28)
    draw_symbol(canvas2, 544, 312, "right", w=28, h=20)
    draw_symbol(canvas2, 596, 312, "left", w=28, h=20)

    detected2 = detect_arrows(canvas2)
    print("Titulo amarelo + setas pequenas, esperado:", expected2)
    print("Detectado:", detected2)
    assert detected2 == expected2, "FALHOU: titulo amarelo venceu a linha real"


if __name__ == "__main__":
    main()
