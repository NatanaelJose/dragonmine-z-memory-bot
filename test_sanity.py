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

    # O nivel 61 observado no jogo mostra 33 posicoes (13 + 13 + 7). O teto
    # antigo de 32 rejeitava essa leitura inteira, deixando o bot sem resposta.
    canvas5 = np.zeros((230, 900, 3), dtype=np.uint8)
    canvas5[:] = (40, 20, 60)
    pattern = ["down", "left", "up", "right"]
    expected5 = [pattern[i % len(pattern)] for i in range(33)]
    row_lengths = (13, 13, 7)
    offset = 0
    for row, row_length in enumerate(row_lengths):
        for column in range(row_length):
            direction = expected5[offset + column]
            draw_symbol(canvas5, 60 + column * 64, 55 + row * 58, direction, w=28, h=28)
        offset += row_length

    detected5 = detect_arrows(canvas5)
    print("sequencia de nivel 61 com 33 elementos:", len(detected5))
    assert detected5 == expected5, "FALHOU: sequencia de 33 elementos foi rejeitada"

    # No nivel 75 existem 40 setas (13 + 13 + 13 + 1). Dois blobs coloridos
    # do texto central podem cair na altura da primeira linha. Quando o nivel
    # esperado e conhecido, a grade regular deve remover esses intrusos.
    canvas6 = np.zeros((290, 1000, 3), dtype=np.uint8)
    canvas6[:] = (40, 20, 60)
    expected6 = [pattern[i % len(pattern)] for i in range(40)]
    row_lengths = (13, 13, 13, 1)
    offset = 0
    for row, row_length in enumerate(row_lengths):
        for column in range(row_length):
            direction = expected6[offset + column]
            draw_symbol(canvas6, 80 + column * 64, 55 + row * 58, direction, w=28, h=28)
        offset += row_length
    draw_symbol(canvas6, 80 + 5 * 64 + 32, 55, "up", w=14, h=24)
    draw_symbol(canvas6, 80 + 8 * 64 + 32, 55, "up", w=14, h=24)

    raw6 = detect_arrows(canvas6)
    corrected6 = detect_arrows(canvas6, expected_sequence_length=40)
    print("nivel 75 com ruido central: bruto=", len(raw6), "corrigido=", len(corrected6))
    assert len(raw6) == 42, "FALHOU: fixture deveria reproduzir dois falsos positivos"
    assert corrected6 == expected6, "FALHOU: grade deveria recuperar exatamente as 40 setas"

    # Texto central pode fazer a primeira linha virar outro componente
    # vertical. A quantidade esperada deve recompor todas as linhas globais.
    canvas7 = np.zeros((330, 1000, 3), dtype=np.uint8)
    canvas7[:] = (40, 20, 60)
    row_y = (45, 158, 216, 274)
    offset = 0
    for row, row_length in enumerate((13, 13, 13, 1)):
        for column in range(row_length):
            direction = expected6[offset + column]
            draw_symbol(canvas7, 80 + column * 64, row_y[row], direction, w=28, h=28)
        offset += row_length
    recovered7 = detect_arrows(canvas7, expected_sequence_length=40)
    print("grade separada em componentes recuperada:", len(recovered7))
    assert recovered7 == expected6, "FALHOU: linhas separadas deveriam formar a grade completa"

    # Uma linha verde semelhante ao placar pode conter 13 blobs regulares,
    # mas seus centros nao se alinham com as colunas repetidas das setas.
    canvas8 = np.zeros((390, 1100, 3), dtype=np.uint8)
    canvas8[:] = (40, 20, 60)
    for column in range(13):
        draw_symbol(canvas8, 190 + column * 40, 35, "down", w=16, h=22)
    offset = 0
    for row, row_length in enumerate((13, 13, 13, 1)):
        for column in range(row_length):
            direction = expected6[offset + column]
            draw_symbol(canvas8, 100 + column * 64, 100 + row * 58, direction, w=28, h=28)
        offset += row_length
    recovered8 = detect_arrows(canvas8, expected_sequence_length=40)
    print("linha de placar desalinhada removida:", len(recovered8))
    assert recovered8 == expected6, "FALHOU: placar nao pode substituir uma linha de setas"

    # Uma linha de HUD com muitos blobs jamais pode acionar combinacoes
    # exponenciais enquanto o flash curto das setas esta na tela.
    noisy_candidates = [
        {"rect": (index * 18, 0, 12, 24)}
        for index in range(32)
    ]
    from arrow_detector import _most_regular_subset
    assert len(_most_regular_subset(noisy_candidates, 13)) == 13

    # Minecraft GUI Scale 2x/3x can fit more than the Auto layout's 13
    # symbols on one line. Expected-length handling must preserve the actual
    # detected rows instead of truncating every row to 13.
    canvas9 = np.zeros((150, 1000, 3), dtype=np.uint8)
    canvas9[:] = (40, 20, 60)
    expected9 = [pattern[i % len(pattern)] for i in range(17)]
    for column, direction in enumerate(expected9):
        draw_symbol(canvas9, 35 + column * 55, 75, direction, w=20, h=28)
    scaled_single = detect_arrows(canvas9, expected_sequence_length=17)
    print("GUI menor com 17 setas na mesma linha:", len(scaled_single))
    assert scaled_single == expected9, "FALHOU: GUI menor nao pode ser truncada em 13"

    canvas10 = np.zeros((220, 1000, 3), dtype=np.uint8)
    canvas10[:] = (40, 20, 60)
    expected10 = [pattern[i % len(pattern)] for i in range(40)]
    offset = 0
    for row, row_length in enumerate((17, 17, 6)):
        for column in range(row_length):
            draw_symbol(
                canvas10,
                35 + column * 55,
                50 + row * 60,
                expected10[offset + column],
                w=20,
                h=28,
            )
        offset += row_length
    scaled_wrapped = detect_arrows(canvas10, expected_sequence_length=40)
    print("GUI menor com linhas 17+17+6:", len(scaled_wrapped))
    assert scaled_wrapped == expected10, "FALHOU: GUI menor deve preservar linhas reais"

    print("OK: filtros de sanidade funcionando")


if __name__ == "__main__":
    main()
