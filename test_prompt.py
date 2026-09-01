"""Teste da deteccao da tela de prompt ('Pressione qualquer tecla...'),
incluindo o caso de falso positivo com outros paineis verdes do jogo
(ex: menu de habilidades) que nao tem texto branco brilhante dentro."""
import cv2
import numpy as np

from arrow_detector import detect_arrows, is_prompt_screen


def main():
    # cena com o painel verde escuro grande + texto branco dentro, como a
    # tela real de "Pressione qualquer tecla para comecar!"
    canvas = np.zeros((450, 850, 3), dtype=np.uint8)
    canvas[:] = (20, 10, 30)
    cv2.rectangle(canvas, (120, 180), (730, 320), (20, 90, 20), -1)  # BGR verde escuro
    cv2.rectangle(canvas, (120, 180), (730, 320), (255, 255, 255), 3)  # borda branca
    cv2.putText(canvas, "Pressione qualquer tecla", (160, 250),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

    print("prompt real, com texto (esperado True):", is_prompt_screen(canvas))
    print("setas nessa tela (esperado vazio):", detect_arrows(canvas))
    assert is_prompt_screen(canvas)

    # painel verde grande SEM texto branco dentro -- simula outro painel do
    # jogo (ex: menu de habilidades) que tem cor parecida mas nao e o prompt
    canvas_menu = np.zeros((450, 850, 3), dtype=np.uint8)
    canvas_menu[:] = (20, 10, 30)
    cv2.rectangle(canvas_menu, (30, 60), (300, 400), (20, 90, 20), -1)
    cv2.rectangle(canvas_menu, (30, 60), (300, 400), (255, 255, 255), 3)
    # texto do titulo do painel em amarelo/laranja (nao branco brilhante)
    cv2.putText(canvas_menu, "Ataques", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)

    print("painel verde sem texto branco (esperado False):", is_prompt_screen(canvas_menu))
    assert not is_prompt_screen(canvas_menu)

    # cena sem prompt (so fundo escuro, tipo jogo normal)
    canvas2 = np.zeros((450, 850, 3), dtype=np.uint8)
    canvas2[:] = (20, 10, 30)
    print("sem prompt (esperado False):", is_prompt_screen(canvas2))
    assert not is_prompt_screen(canvas2)

    # menu de estatisticas real: VARIOS paineis verdes lado a lado, mais
    # quadrados que a faixa horizontal do prompt, com bastante texto branco
    # e numeros dentro -- isso e o caso real que deu falso positivo
    canvas_stats = np.zeros((470, 821, 3), dtype=np.uint8)
    canvas_stats[:] = (30, 20, 10)
    panels = [(10, 10, 260, 200), (280, 10, 550, 90), (560, 10, 810, 460), (10, 220, 260, 460)]
    for (x1, y1, x2, y2) in panels:
        cv2.rectangle(canvas_stats, (x1, y1), (x2, y2), (20, 90, 20), -1)
        cv2.rectangle(canvas_stats, (x1, y1), (x2, y2), (255, 255, 255), 3)
        cv2.putText(canvas_stats, "31", (x1 + 20, y1 + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(canvas_stats, "Nivel 15", (x1 + 20, y1 + 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    print("menu de estatisticas, varios paineis (esperado False):", is_prompt_screen(canvas_stats))
    assert not is_prompt_screen(canvas_stats)

    print("OK: deteccao de prompt bateu com o esperado em todos os casos")


if __name__ == "__main__":
    main()
