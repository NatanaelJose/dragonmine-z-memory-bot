"""Configuracoes ajustaveis do bot do minigame de memoria (DragonMine Z)."""

# Tecla do SO para cada direcao detectada. Troque aqui se o mod usar outro bind.
KEY_MAP = {
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
}

# Delay entre cada tecla enviada (segundos). Ajuste se o jogo nao registrar a tempo.
KEY_PRESS_DELAY = 0.12
KEY_HOLD_TIME = 0.05

# Intervalo do polling de tela (segundos). Cada frame custa so ~10-15ms
# para capturar + detectar, entao 0.05s (20 checagens/s) da folga e ainda
# reage rapido ao aparecer/sumir das setas.
POLL_INTERVAL = 0.05
