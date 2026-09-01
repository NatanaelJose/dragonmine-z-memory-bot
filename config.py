"""Configuracoes ajustaveis do bot do minigame de memoria (DragonMine Z)."""

# Tecla do SO para cada direcao detectada. Troque aqui se o mod usar outro bind.
KEY_MAP = {
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
}

# Delay entre cada tecla enviada (segundos). Ajuste se o jogo nao registrar a tempo.
# Perfis confirmados no jogo. 0.02/0.02 ja perde entradas; 0.03/0.03 e o
# limite rapido observado. O usuario pode escolher o perfil pela CLI ou
# informar valores personalizados sem editar este arquivo.
SPEED_PROFILES = {
    "fast": {"hold_time": 0.03, "key_delay": 0.03},
    "safe": {"hold_time": 0.05, "key_delay": 0.05},
}
DEFAULT_SPEED_PROFILE = "fast"

# Compatibilidade com as ferramentas que usam diretamente os valores padrao.
KEY_HOLD_TIME = SPEED_PROFILES[DEFAULT_SPEED_PROFILE]["hold_time"]
KEY_PRESS_DELAY = SPEED_PROFILES[DEFAULT_SPEED_PROFILE]["key_delay"]

# Intervalo do polling de tela (segundos). Cada frame custa so ~10-15ms
# para capturar + detectar, entao 0.05s (20 checagens/s) da folga e ainda
# reage rapido ao aparecer/sumir das setas.
POLL_INTERVAL = 0.05
