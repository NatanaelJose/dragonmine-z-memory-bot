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
from autonomy import handle_prompt
from capture import grab_window, memory_capture_rect
from config import (
    DEFAULT_SPEED_PROFILE,
    KEY_HOLD_TIME,
    KEY_MAP as KEY_NAME_MAP,
    KEY_PRESS_DELAY,
    MAX_POLL_INTERVAL,
    POLL_INTERVAL,
    SPEED_PROFILES,
)
from rhythm_capture import DEFAULT_DURATION, DEFAULT_FPS, record_rhythm_session
from rhythm_bot import run_rhythm
from level_progress import (
    LevelProgress,
    expected_arrows_for_level,
    sequence_limit_for_target,
    wrong_direction_for,
)
from memory_debug import save_memory_debug
from input_pause import EscapePauseGuard
from window import focus_game_window, get_window_rect

PYNPUT_KEYS = {
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
}
KEY_MAP = {direction: PYNPUT_KEYS[key_name] for direction, key_name in KEY_NAME_MAP.items()}

keyboard = Controller()


def release_gameplay_keys():
    for key in (*KEY_MAP.values(), Key.space):
        keyboard.release(key)


def press_sequence(
    directions,
    hold_time=KEY_HOLD_TIME,
    key_delay=KEY_PRESS_DELAY,
    pause_guard=None,
):
    log(f"Enviando sequencia: {directions}")
    started_at = time.perf_counter()
    for index, direction in enumerate(directions):
        if pause_guard is not None:
            pause_guard.wait_if_paused(release_gameplay_keys)
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


def collect_sequence_until_clear(
    sct,
    initial_frame,
    initial_sequence,
    sequence_limit,
    expected_count,
    timeout=10,
):
    """Keep the fullest frame seen during Memorize and wait for a true clear."""
    best_sequence = list(initial_sequence)
    best_frame = initial_frame.copy()
    deadline = time.perf_counter() + timeout
    empty_since = None
    while time.perf_counter() < deadline:
        window_rect = get_window_rect()
        if window_rect is None:
            return best_sequence, best_frame, False
        frame = grab_window(sct, memory_capture_rect(window_rect, expected_count))
        directions = detect_arrows(
            frame,
            sequence_limit,
            expected_count,
        )
        now = time.perf_counter()
        if directions:
            if len(directions) > len(best_sequence):
                best_sequence = directions
                best_frame = frame.copy()
        if len(directions) == expected_count:
            empty_since = None
        elif empty_since is None:
            empty_since = now
        elif now - empty_since >= 0.12:
            return best_sequence, best_frame, True
        time.sleep(0.002)
    return best_sequence, best_frame, False


def submit_forced_failure(captured_sequence, hold_time, key_delay):
    """Send exactly one guaranteed-wrong key, then stop producing input.

    DragonMine ends the round on the first wrong key. Sending the remainder of
    a fabricated sequence races the result screen and can move the selection in
    the minigame menu before autonomous recovery gets a chance to click it.
    """
    wrong_direction = wrong_direction_for(captured_sequence[0])
    press_sequence([wrong_direction], hold_time, key_delay)
    return wrong_direction


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


def run(
    verbose=False,
    hold_time=KEY_HOLD_TIME,
    key_delay=KEY_PRESS_DELAY,
    poll_interval=POLL_INTERVAL,
    autonomous=False,
    target_level=None,
):
    print("Bot iniciado. Localizando janela do jogo...", flush=True)
    print(
        f"Velocidade: hold={hold_time:.3f}s intervalo={key_delay:.3f}s "
        f"captura={poll_interval:.3f}s",
        flush=True,
    )
    sequence_limit = sequence_limit_for_target(target_level)
    if target_level is not None:
        log(f"LEVEL:CAPACITY target={target_level} max_arrows={sequence_limit}")
    wait_for_window()
    print("Janela encontrada. Pressione Ctrl+C aqui no terminal para parar.", flush=True)

    with EscapePauseGuard(log) as pause_guard, mss.MSS() as sct:
        progress = LevelProgress(target_level)
        last_prompt_check = 0.0
        while True:
            pause_guard.wait_if_paused(release_gameplay_keys)
            window_rect = get_window_rect()
            if window_rect is None:
                log("Janela do jogo sumiu, aguardando ela voltar...")
                wait_for_window()
                continue

            # Arrow flashes become shorter at advanced levels. Scan only the
            # central play field on every cycle and pay the full-frame cost
            # for prompt/autonomy detection a few times per second.
            now = time.perf_counter()
            prompt = False
            if now - last_prompt_check >= 0.20:
                full_frame = grab_window(sct, window_rect)
                prompt = is_prompt_screen(full_frame)
                last_prompt_check = now
            directions = []
            memory_frame = None
            if not prompt:
                candidate_level = progress.current_level + 1 if progress.current_level else 1
                expected_count = expected_arrows_for_level(candidate_level)
                memory_frame = grab_window(
                    sct,
                    memory_capture_rect(window_rect, expected_count),
                )
                directions = detect_arrows(
                    memory_frame,
                    sequence_limit,
                    expected_count,
                )
                if len(directions) != expected_count:
                    directions = []

            if verbose:
                log(f"prompt={prompt} setas={directions}")

            # Checa a tela de prompt ("Pressione qualquer tecla...", inicio
            # ou fim de jogo) SEMPRE primeiro, antes de esperar por setas --
            # senao o bot fica preso para sempre se o jogo comecar direto
            # nessa tela (nunca vai ter seta ate alguem apertar uma tecla).
            if prompt:
                log("Tela 'Pressione qualquer tecla...' detectada, avancando...")
                had_active_run = progress.current_level > 0
                restarted = handle_prompt(
                    sct,
                    window_rect,
                    "memory",
                    press_any_key,
                    autonomous,
                    log,
                )
                if restarted or had_active_run:
                    progress.reset_run()
                    log(f"LEVEL:RUN_RESET record={progress.best_completed}")
                last_prompt_check = 0.0
                continue

            if not directions:
                time.sleep(poll_interval)
                continue

            update = progress.begin_round()
            if update.completed_level is not None:
                log(
                    f"LEVEL:COMPLETED level={update.completed_level} "
                    f"record={progress.best_completed}"
                )
            if update.target_reached:
                log(f"LEVEL:TARGET_REACHED level={progress.best_completed}")
                if not autonomous:
                    return
                log("LEVEL:TARGET_RESET aguardando Repita para reiniciar o teste.")
                best_sequence, _, cleared = collect_sequence_until_clear(
                    sct,
                    memory_frame,
                    directions,
                    sequence_limit,
                    expected_arrows_for_level(progress.run_completed + 1),
                )
                if not cleared:
                    log("LEVEL:TARGET_RESET_CANCELLED setas nao sumiram; nenhum input enviado.")
                    return
                focus_game_window()
                wrong_direction = submit_forced_failure(
                    best_sequence,
                    hold_time,
                    key_delay,
                )
                log(
                    f"LEVEL:FORCED_RESET expected={best_sequence[0]} "
                    f"sent={wrong_direction} sent_count=1"
                )
                log("LEVEL:RECOVERY_WAIT aguardando a tela final sem enviar mais teclas.")
                continue
            log(f"LEVEL:CURRENT level={update.current_level} target={target_level or 0}")
            expected_count = expected_arrows_for_level(update.current_level)
            print("=" * 50)
            log(
                f"MEMORIZE detectado -- coletando rajada: "
                f"inicial={len(directions)} esperado={expected_count}"
            )
            print("=" * 50)

            # So envia a sequencia depois que as setas sumirem da tela --
            # isso e o que marca o fim do 'Memorize!' e o inicio do
            # 'Repita!'. Enviar durante o proprio 'Memorize!' e cedo demais
            # e o jogo pode nao aceitar o input nessa fase.
            log("Aguardando as setas sumirem (fim do 'Memorize!')...")
            best_sequence, best_frame, cleared = collect_sequence_until_clear(
                sct,
                memory_frame,
                directions,
                sequence_limit,
                expected_count,
            )
            if not cleared:
                log(
                    f"LEVEL:DEBUG_STOP level={update.current_level} "
                    "motivo=timeout_ou_janela_perdida"
                )
                return
            if len(best_sequence) != expected_count:
                log(
                    f"LEVEL:CAPTURE_MISMATCH level={update.current_level} "
                    f"expected={expected_count} captured={len(best_sequence)}"
                )
                if autonomous:
                    focus_game_window()
                    wrong_direction = submit_forced_failure(
                        best_sequence,
                        hold_time,
                        key_delay,
                    )
                    log(
                        f"LEVEL:CAPTURE_RETRY record={progress.best_completed} "
                        f"expected_first={best_sequence[0]} "
                        f"sent={wrong_direction} sent_count=1"
                    )
                    log("LEVEL:RECOVERY_WAIT aguardando a tela final sem enviar mais teclas.")
                    continue
                log(f"LEVEL:DEBUG_STOP record={progress.best_completed}")
                return
            if update.current_level >= 120:
                try:
                    debug_root = save_memory_debug(
                        best_frame,
                        update.current_level,
                        expected_count,
                        best_sequence,
                        sequence_limit,
                    )
                    log(f"LEVEL:DEBUG_SAVED level={update.current_level} path={debug_root}")
                except OSError as error:
                    log(f"LEVEL:DEBUG_SAVE_FAILED {error}")
            log(
                f"MEMORIZE completo level={update.current_level} "
                f"captured={len(best_sequence)} sequence={best_sequence}"
            )

            log("Setas sumiram -- fase 'Repita!' comecou, enviando sequencia...")
            focus_game_window()
            press_sequence(best_sequence, hold_time, key_delay, pause_guard)

            # espera mais um pouco para nao reler a mesma tela de transicao
            # (ex: tela de resultado aparecendo) como se fosse novo memorize
            time.sleep(0.3)


def parse_args():
    parser = argparse.ArgumentParser(description="Bot do minigame de memoria DragonMine Z")
    parser.add_argument(
        "--game",
        choices=("memory", "rhythm", "rhythm-capture"),
        default="memory",
        help="modo executado pelo controlador desktop",
    )
    parser.add_argument(
        "--speed",
        choices=sorted(SPEED_PROFILES),
        default=DEFAULT_SPEED_PROFILE,
        help=f"perfil de velocidade (padrao: {DEFAULT_SPEED_PROFILE})",
    )
    parser.add_argument("--hold-time", type=float, help="tempo personalizado segurando cada tecla")
    parser.add_argument("--key-delay", type=float, help="intervalo personalizado entre teclas")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=POLL_INTERVAL,
        help=f"intervalo entre capturas em segundos (padrao: {POLL_INTERVAL})",
    )
    parser.add_argument(
        "--capture-duration",
        type=float,
        default=DEFAULT_DURATION,
        help="duracao da amostra do modo ritmo em segundos",
    )
    parser.add_argument(
        "--capture-fps",
        type=float,
        default=DEFAULT_FPS,
        help="FPS alvo da amostra do modo ritmo",
    )
    parser.add_argument(
        "--rhythm-lead-ms",
        type=float,
        default=8.0,
        help="antecipacao do input de ritmo em milissegundos",
    )
    parser.add_argument(
        "--autonomous",
        action="store_true",
        help="reinicia automaticamente o minigame depois de uma falha",
    )
    parser.add_argument(
        "--target-level",
        type=int,
        help="encerra depois de confirmar que este nivel foi concluido",
    )
    args = parser.parse_args()

    profile = SPEED_PROFILES[args.speed]
    hold_time = args.hold_time if args.hold_time is not None else profile["hold_time"]
    key_delay = args.key_delay if args.key_delay is not None else profile["key_delay"]
    if hold_time <= 0 or key_delay < 0:
        parser.error("--hold-time deve ser > 0 e --key-delay deve ser >= 0")
    if not 0 <= args.poll_interval <= MAX_POLL_INTERVAL:
        parser.error(f"--poll-interval deve ficar entre 0 e {MAX_POLL_INTERVAL}")
    if not -50 <= args.rhythm_lead_ms <= 100:
        parser.error("--rhythm-lead-ms deve ficar entre -50 e 100")
    if args.target_level is not None and not 1 <= args.target_level <= 999:
        parser.error("--target-level deve ficar entre 1 e 999")
    return args, hold_time, key_delay


if __name__ == "__main__":
    try:
        selected_args, selected_hold, selected_delay = parse_args()
        if selected_args.game == "rhythm-capture":
            record_rhythm_session(selected_args.capture_duration, selected_args.capture_fps)
        elif selected_args.game == "rhythm":
            run_rhythm(selected_args.rhythm_lead_ms, autonomous=selected_args.autonomous)
        else:
            run(
                hold_time=selected_hold,
                key_delay=selected_delay,
                poll_interval=selected_args.poll_interval,
                autonomous=selected_args.autonomous,
                target_level=selected_args.target_level,
            )
    except KeyboardInterrupt:
        print("\nBot encerrado.")
