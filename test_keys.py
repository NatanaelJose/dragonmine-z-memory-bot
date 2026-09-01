"""
Teste isolado de envio de teclas via pynput, sem depender de deteccao de
tela: espera N segundos (pra voce trocar de janela e focar o Minecraft) e
depois envia uma sequencia fixa de teclas de seta. Serve para confirmar que
o pynput realmente funciona no jogo antes de testar o bot completo.

Uso: python test_keys.py [segundos] [sequencia]
Exemplo: python test_keys.py 10 left,left,down
"""
import sys
import time

from pynput.keyboard import Controller, Key

from config import KEY_HOLD_TIME, KEY_MAP, KEY_PRESS_DELAY

PYNPUT_KEYS = {
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
}

keyboard = Controller()


def countdown(seconds):
    for remaining in range(seconds, 0, -1):
        print(f"  Troque para o Minecraft agora... enviando teclas em {remaining}s", end="\r")
        time.sleep(1)
    print(" " * 70, end="\r")


def press_sequence(directions):
    print(f"Enviando sequencia: {directions}")
    for direction in directions:
        key_name = KEY_MAP.get(direction)
        key = PYNPUT_KEYS.get(key_name)
        if key is None:
            print(f"  ! direcao desconhecida: {direction}, pulando")
            continue
        print(f"  -> {direction}")
        keyboard.press(key)
        time.sleep(KEY_HOLD_TIME)
        keyboard.release(key)
        time.sleep(KEY_PRESS_DELAY)
    print("Sequencia enviada.")


def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    sequence = sys.argv[2].split(",") if len(sys.argv) > 2 else ["left", "left"]

    print(f"Vai enviar {sequence} depois de {seconds}s.")
    countdown(seconds)
    press_sequence(sequence)


if __name__ == "__main__":
    main()
