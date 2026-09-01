"""
Bot para o minigame de memoria de setas do mod Dragon Ball (DragonMine Z).

Nao precisa de calibracao de regiao: a janela do jogo e localizada
automaticamente pelo titulo e escaneada inteira a cada frame. A logica de
estado usa so a presenca/ausencia de simbolos coloridos na tela:

  TELA_DE_PROMPT   -> 'Pressione qualquer tecla...' (inicio ou fim de
                       jogo): aperta uma tecla para avancar.
  SETAS_APARECEM   -> fase 'Memorize!': faz UMA UNICA leitura da tela
                       nesse instante e usa como a sequencia, enviando as
                       teclas na sequencia.

Pare o bot a qualquer momento com Ctrl+C no terminal.
"""
import argparse
import time

import mss
from pynput.keyboard import Controller, Key

from arrow_detector import detect_arrows, is_prompt_screen
from capture import grab_window
from config import (
    DEFAULT_SPEED_PROFILE,
    KEY_HOLD_TIME,
    KEY_MAP as KEY_NAME_MAP,
    KEY_PRESS_DELAY,
    POLL_INTERVAL,
    SPEED_PROFILES,
)
from window import focus_game_window, get_window_rect

PYNPUT_KEYS = {
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
}
KEY_MAP = {direction: PYNPUT_KEYS[key_name] for direction, key_name in KEY_NAME_MAP.items()}

keyboard = Controller()


def press_sequence(directions, hold_time=KEY_HOLD_TIME, key_delay=KEY_PRESS_DELAY):
    log(f"Enviando sequencia: {directions}")
    started_at = time.perf_counter()
    for index, direction in enumerate(directions):
        key = KEY_MAP.get(direction)
        if key is None:
            log(f"  ! direcao desconhecida: {direction}, pulando")
            continue
        keyboard.press(key)
        time.sleep(hold_time)
        keyboard.release(key)
        if index < len(directions) - 1:
            time.sleep(key_delay)
    log(f"Sequencia enviada em {time.perf_counter() - started_at:.2f}s")


def press_any_key():
    keyboard.press(Key.space)
    time.sleep(KEY_HOLD_TIME)
    keyboard.release(Key.space)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def wait_for_window():
    last_warn = 0
    while True:
        rect = get_window_rect()
        if rect is not None:
            return rect
        now = time.time()
        if now - last_warn > 5:
            print("Janela do jogo (titulo com 'DragonMine') nao encontrada. Abra o jogo...", flush=True)
            last_warn = now
        time.sleep(1)


def run(verbose=True, hold_time=KEY_HOLD_TIME, key_delay=KEY_PRESS_DELAY):
    print("Bot iniciado. Localizando janela do jogo...", flush=True)
    print(f"Velocidade: hold={hold_time:.3f}s intervalo={key_delay:.3f}s", flush=True)
    wait_for_window()
    print("Janela encontrada. Pressione Ctrl+C aqui no terminal para parar.", flush=True)

    with mss.mss() as sct:
        while True:
            window_rect = get_window_rect()
            if window_rect is None:
                log("Janela do jogo sumiu, aguardando ela voltar...")
                wait_for_window()
                continue

            frame = grab_window(sct, window_rect)
            prompt = is_prompt_screen(frame)
            directions = detect_arrows(frame) if not prompt else []

            if verbose:
                log(f"prompt={prompt} setas={directions}")

            # Checa a tela de prompt ("Pressione qualquer tecla...", inicio
            # ou fim de jogo) SEMPRE primeiro, antes de esperar por setas --
            # senao o bot fica preso para sempre se o jogo comecar direto
            # nessa tela (nunca vai ter seta ate alguem apertar uma tecla).
            if prompt:
                log("Tela 'Pressione qualquer tecla...' detectada, avancando...")
                focus_game_window()
                time.sleep(0.3)
                press_any_key()

                # espera a tela de prompt REALMENTE sumir antes de continuar
                # -- se so desse um sleep fixo, um frame de transicao ainda
                # mostrando o painel poderia disparar outro press_any_key(),
                # mandando uma tecla extra bem no meio do 'Memorize!'
                wait_start = time.time()
                while time.time() - wait_start < 5:
                    still_prompt = is_prompt_screen(grab_window(sct, get_window_rect() or window_rect))
                    if verbose:
                        log(f"  aguardando prompt sumir... ainda visivel={still_prompt}")
                    if not still_prompt:
                        break
                    time.sleep(POLL_INTERVAL)

                continue

            if not directions:
                time.sleep(POLL_INTERVAL)
                continue

            # Uma unica leitura: assim que ve setas, usa exatamente essa
            # leitura como a sequencia (sem tentar estabilizar varios
            # frames). Simples e direto -- se a leitura vier incompleta ou
            # errada, ajustamos o timing depois com base no que acontecer.
            best_sequence = directions
            print("=" * 50)
            log(f"MEMORIZE detectado -- leitura unica: {best_sequence}")
            print("=" * 50)

            # So envia a sequencia depois que as setas sumirem da tela --
            # isso e o que marca o fim do 'Memorize!' e o inicio do
            # 'Repita!'. Enviar durante o proprio 'Memorize!' e cedo demais
            # e o jogo pode nao aceitar o input nessa fase.
            log("Aguardando as setas sumirem (fim do 'Memorize!')...")
            wait_start = time.time()
            while time.time() - wait_start < 10:
                window_rect = get_window_rect()
                if window_rect is None:
                    break
                if not detect_arrows(grab_window(sct, window_rect)):
                    break
                time.sleep(POLL_INTERVAL)

            log("Setas sumiram -- fase 'Repita!' comecou, enviando sequencia...")
            focus_game_window()
            press_sequence(best_sequence, hold_time, key_delay)

            # espera mais um pouco para nao reler a mesma tela de transicao
            # (ex: tela de resultado aparecendo) como se fosse novo memorize
            time.sleep(0.3)


def parse_speed_args():
    parser = argparse.ArgumentParser(description="Bot do minigame de memoria DragonMine Z")
    parser.add_argument(
        "--speed",
        choices=sorted(SPEED_PROFILES),
        default=DEFAULT_SPEED_PROFILE,
        help=f"perfil de velocidade (padrao: {DEFAULT_SPEED_PROFILE})",
    )
    parser.add_argument("--hold-time", type=float, help="tempo personalizado segurando cada tecla")
    parser.add_argument("--key-delay", type=float, help="intervalo personalizado entre teclas")
    args = parser.parse_args()

    profile = SPEED_PROFILES[args.speed]
    hold_time = args.hold_time if args.hold_time is not None else profile["hold_time"]
    key_delay = args.key_delay if args.key_delay is not None else profile["key_delay"]
    if hold_time <= 0 or key_delay < 0:
        parser.error("--hold-time deve ser > 0 e --key-delay deve ser >= 0")
    return hold_time, key_delay


if __name__ == "__main__":
    try:
        selected_hold, selected_delay = parse_speed_args()
        run(hold_time=selected_hold, key_delay=selected_delay)
    except KeyboardInterrupt:
        print("\nBot encerrado.")
