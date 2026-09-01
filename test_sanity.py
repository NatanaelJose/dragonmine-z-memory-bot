"""Teste dos filtros de sanidade: rejeita sequencias longas demais ou com
todos os elementos identicos (sinais de ruido, nao de um nivel real)."""
import cv2
import numpy as np

from arrow_detector import analyze_arrow_candidates, detect_arrows
from test_detector import draw_symbol


def main():
    # 10 simbolos amarelos (up) identicos -- cenario real que causou bug.
    # Mesmo estando abaixo do teto atual, devem ser rejeitados por repeticao.
    canvas = np.zeros((120, 1200, 3), dtype=np.uint8)
    canvas[:] = (40, 20, 60)
    for i in range(10):
        draw_symbol(canvas, 60 + i * 60, 60, "up")

    detected = detect_arrows(canvas)
    print("10x 'up' identicos (esperado vazio, ruido):", detected)
    assert detected == [], "FALHOU: deveria rejeitar sequencia longa e identica"

    analysis = analyze_arrow_candidates(canvas)
    direction_candidates = [
        candidate for candidate in analysis["candidates"]
        if candidate["direction"] is not None
    ]
    assert analysis["directions"] == []
    assert len(direction_candidates) == 10
    assert all(not candidate["accepted"] for candidate in direction_candidates)
    assert all(candidate["reason"] == "3+ direcoes identicas" for candidate in direction_candidates)

    # sequencia real e valida (poucos elementos, direcoes variadas)
    canvas2 = np.zeros((120, 500, 3), dtype=np.uint8)
    canvas2[:] = (40, 20, 60)
    expected = ["down", "left", "up"]
    for i, direction in enumerate(expected):
        draw_symbol(canvas2, 70 + i * 110, 60, direction)

    detected2 = detect_arrows(canvas2)
    print("sequencia real valida (esperado", expected, "):", detected2)
    assert detected2 == expected, "FALHOU: sequencia real nao deveria ser rejeitada"

    analysis2 = analyze_arrow_candidates(canvas2)
    accepted = sorted(
        (candidate for candidate in analysis2["candidates"] if candidate["accepted"]),
        key=lambda candidate: candidate["rect"][0],
    )
    assert analysis2["directions"] == expected
    assert [candidate["direction"] for candidate in accepted] == expected
    assert all(candidate["reason"] == "aceito" for candidate in accepted)

    # Nivel 13 observado no jogo exibe 9 simbolos. Sequencias avancadas,
    # desde que variadas, nao podem ser confundidas com ruido longo.
    canvas3 = np.zeros((120, 800, 3), dtype=np.uint8)
    canvas3[:] = (40, 20, 60)
    # Padrao real observado: inclui 3x "up" consecutivos, o que e valido.
    # A protecao so deve rejeitar quando a sequencia INTEIRA for identica.
    expected3 = ["down", "left", "down", "up", "up", "up", "left", "down", "up"]
    for i, direction in enumerate(expected3):
        draw_symbol(canvas3, 45 + i * 82, 60, direction, w=28, h=28)

    detected3 = detect_arrows(canvas3)
    print("sequencia avancada de 9 elementos:", detected3)
    assert detected3 == expected3, "FALHOU: sequencia valida de 9 elementos foi rejeitada"

    # Ao ultrapassar a largura disponivel, o jogo continua em uma nova
    # linha. A ordem correta e esq->dir na primeira e depois na segunda.
    canvas4 = np.zeros((180, 800, 3), dtype=np.uint8)
    canvas4[:] = (40, 20, 60)
    first_row = expected3
    second_row = ["right", "down", "up", "left"]
    for i, direction in enumerate(first_row):
        draw_symbol(canvas4, 45 + i * 82, 55, direction, w=28, h=28)
    for i, direction in enumerate(second_row):
        draw_symbol(canvas4, 45 + i * 82, 105, direction, w=28, h=28)

    expected4 = first_row + second_row
    detected4 = detect_arrows(canvas4)
    print("sequencia de 13 elementos em duas linhas:", detected4)
    assert detected4 == expected4, "FALHOU: ordem de leitura entre linhas incorreta"

    print("OK: filtros de sanidade funcionando")


if __name__ == "__main__":
    main()
