"""Deteccao das setas coloridas do minigame de memoria via OpenCV."""
import cv2
import numpy as np

# Pixel considerado "seta" se tiver saturacao e brilho altos (cores vivas
# sobre o fundo escuro translucido do jogo: magenta, amarelo, ciano, verde...)
SAT_MIN = 90
VAL_MIN = 90
MIN_BLOB_AREA = 40

# Filtros de forma/tamanho para descartar blobs que nao sao setas (texto
# "Nivel X", barra de progresso, paineis de UI/menu) ao escanear a janela
# inteira sem regiao calibrada. Os sprites reais do jogo tem ~40-60px de
# lado nas resolucoes observadas -- ajuste MAX_BLOB_* se a janela do jogo
# for muito maior/menor que isso.
MIN_BLOB_HEIGHT = 20
MIN_BLOB_WIDTH = 15
MAX_BLOB_HEIGHT = 100
MAX_BLOB_WIDTH = 100
MAX_ASPECT_RATIO = 2.2  # w/h ou h/w -- setas sao proximas de quadradas; a
                         # barra de progresso e muito mais larga que alta

# O nivel mais facil do minigame sempre mostra pelo menos 3 setas -- exigir
# esse minimo descarta a maioria do ruido aleatorio do HUD normal do jogo
# (hotbar, minimapa, icones de item) que por coincidencia tem 1-2 blobs
# parecidos com seta, sem exigir calibrar uma regiao especifica da tela.
MIN_SEQUENCE_LENGTH = 3
# Limite superior de sanidade -- os niveis do minigame nao devem passar
# disso; uma leitura maior que isso e sinal de ruido (varios elementos da
# tela normal do jogo, ex: HUD/texto, sendo confundidos com setas de uma vez).
# Niveis avancados chegam a pelo menos 9 simbolos e quebram a sequencia em
# mais de uma linha quando falta espaco horizontal. O teto continua sendo
# apenas uma protecao contra leituras absurdas de HUD/texto.
MAX_SEQUENCE_LENGTH = 32

# Cada direcao tem SEMPRE a mesma cor neste mod (confirmado jogando varios
# niveis) -- entao a direcao e lida direto da cor do simbolo, sem precisar
# analisar a forma (mais rapido e mais robusto que o pico de largura usado
# antes, que era sensivel a variacoes sutis do sprite).
# Faixas de matiz (H) no espaco HSV do OpenCV (0-179):
#   verde   (~35-85)   -> down
#   ciano   (~86-100)  -> left
#   magenta (~140-170) -> right
#   amarelo (~20-34, o simbolo de cruz) -> up
COLOR_HUE_RANGES = {
    "down": (35, 85),
    "left": (86, 100),
    "right": (140, 170),
    "up": (20, 34),
}


def _colored_mask(bgr_image):
    hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
    lower = np.array([0, SAT_MIN, VAL_MIN])
    upper = np.array([179, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return mask


def _direction_from_blob(bgr_image, mask, x, y, w, h):
    """Determina a direcao pela cor media do simbolo -- cada direcao tem
    sempre a mesma cor neste mod, entao basta olhar o matiz (H) dominante e
    mapear direto, sem analisar a forma do sprite."""
    roi_mask = mask[y:y + h, x:x + w] > 0
    if not roi_mask.any():
        return None

    hsv_roi = cv2.cvtColor(bgr_image[y:y + h, x:x + w], cv2.COLOR_BGR2HSV)
    hues = hsv_roi[:, :, 0][roi_mask]
    if len(hues) == 0:
        return None
    mean_hue = float(np.median(hues))

    for direction, (low, high) in COLOR_HUE_RANGES.items():
        if low <= mean_hue <= high:
            return direction
    return None


def _keep_main_row(blobs, y_tolerance=15):
    """As setas do minigame ficam sempre alinhadas na mesma linha horizontal
    e proximas umas das outras. Ao escanear a janela toda (sem regiao
    calibrada), pode haver ruido colorido espalhado (HUD, itens, blocos) --
    entao agrupamos os blobs por altura Y similar e ficamos com o MAIOR
    grupo (as setas de verdade sempre aparecem juntas; ruido de fundo tende
    a estar espalhado e nao forma um grupo grande na mesma altura)."""
    if len(blobs) <= 1:
        return blobs

    groups = []  # cada grupo: lista de blobs com centro Y proximo
    for blob in blobs:
        x, y, w, h = blob
        cy = y + h / 2.0
        placed = False
        for group in groups:
            group_cy = sum(b[1] + b[3] / 2.0 for b in group) / len(group)
            if abs(cy - group_cy) <= y_tolerance:
                group.append(blob)
                placed = True
                break
        if not placed:
            groups.append([blob])

    if not groups:
        return []

    best_group = max(groups, key=len)
    if len(best_group) < 2:
        return []  # um unico blob isolado provavelmente e ruido, nao seta

    # dentro do grupo, os sprites de seta tem todos tamanho parecido --
    # descarta quem destoar muito da altura mediana do grupo (ruido que por
    # coincidencia caiu na mesma faixa Y)
    heights = sorted(b[3] for b in best_group)
    median_h = heights[len(heights) // 2]
    return [b for b in best_group if abs(b[3] - median_h) <= median_h * 0.4]


def _group_candidate_rows(candidates, y_tolerance=15):
    """Agrupa candidatos por linha sem decidir antecipadamente qual vence.

    Uma tela pode ter uma linha maior de ruido (por exemplo, as letras
    amarelas de "Boxe Sombrio") e uma linha menor contendo as setas reais.
    Por isso todas as linhas precisam passar pelos filtros de sequencia.
    """
    groups = []
    for candidate in candidates:
        x, y, w, h = candidate["rect"]
        cy = y + h / 2.0
        for group in groups:
            group_cy = sum(
                item["rect"][1] + item["rect"][3] / 2.0 for item in group
            ) / len(group)
            if abs(cy - group_cy) <= y_tolerance:
                group.append(candidate)
                break
        else:
            groups.append([candidate])

    rows = []
    for group in groups:
        heights = sorted(item["rect"][3] for item in group)
        median_h = heights[len(heights) // 2]
        row = []
        for candidate in group:
            if abs(candidate["rect"][3] - median_h) <= median_h * 0.4:
                row.append(candidate)
            else:
                candidate["reason"] = "altura fora da mediana"
        if row:
            rows.append(row)
    return rows


def analyze_arrow_candidates(bgr_image):
    """Analisa as setas e explica a decisao tomada para cada contorno.

    O retorno contem ``directions``, ``mask`` e ``candidates``. Cada
    candidato informa seu retangulo, area, direcao (quando reconhecida),
    se foi aceito e o motivo. Esta e a mesma analise usada por
    :func:`detect_arrows`, para o overlay de debug nunca divergir do bot.
    """
    mask = _colored_mask(bgr_image)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    blobs = []
    for c in contours:
        area = cv2.contourArea(c)
        x, y, w, h = cv2.boundingRect(c)
        candidate = {
            "rect": (x, y, w, h),
            "area": float(area),
            "direction": None,
            "accepted": False,
            "reason": "candidato geometrico",
        }
        candidates.append(candidate)

        if area < MIN_BLOB_AREA:
            candidate["reason"] = f"area {area:.0f} < {MIN_BLOB_AREA}"
            continue
        if h < MIN_BLOB_HEIGHT or w < MIN_BLOB_WIDTH:
            candidate["reason"] = f"pequeno {w}x{h}"
            continue
        if h > MAX_BLOB_HEIGHT or w > MAX_BLOB_WIDTH:
            candidate["reason"] = f"grande {w}x{h}"
            continue
        aspect = max(w / h, h / w)
        if aspect > MAX_ASPECT_RATIO:
            candidate["reason"] = f"proporcao {aspect:.1f} > {MAX_ASPECT_RATIO}"
            continue
        blobs.append(candidate)

    analyzed_rows = []
    for row in _group_candidate_rows(blobs):
        row.sort(key=lambda candidate: candidate["rect"][0])
        direction_candidates = []
        directions = []
        for candidate in row:
            x, y, w, h = candidate["rect"]
            direction = _direction_from_blob(bgr_image, mask, x, y, w, h)
            if direction:
                candidate["direction"] = direction
                direction_candidates.append(candidate)
                directions.append(direction)
            else:
                candidate["reason"] = "cor fora das faixas"

        if not direction_candidates:
            continue

        center_y = float(np.median([
            item["rect"][1] + item["rect"][3] / 2.0
            for item in direction_candidates
        ]))
        symbol_size = float(np.median([
            max(item["rect"][2], item["rect"][3])
            for item in direction_candidates
        ]))
        analyzed_rows.append({
            "center_y": center_y,
            "symbol_size": symbol_size,
            "directions": directions,
            "candidates": direction_candidates,
        })

    # Linhas consecutivas das setas ficam proximas verticalmente e usam os
    # mesmos sprites. Formamos componentes de linhas compativeis antes de
    # validar comprimento/repeticao, pois a ultima linha pode ter so 1-2
    # simbolos quando a sequencia acabou de quebrar para baixo.
    analyzed_rows.sort(key=lambda item: item["center_y"])
    row_components = []
    for row in analyzed_rows:
        if not row_components:
            row_components.append([row])
            continue
        previous = row_components[-1][-1]
        size_ratio = row["symbol_size"] / previous["symbol_size"]
        max_row_gap = max(60.0, max(row["symbol_size"], previous["symbol_size"]) * 3.5)
        row_gap = row["center_y"] - previous["center_y"]
        if row_gap <= max_row_gap and 0.65 <= size_ratio <= 1.55:
            row_components[-1].append(row)
        else:
            row_components.append([row])

    valid_components = []
    for component in row_components:
        directions = []
        direction_candidates = []
        gap_variations = []
        for row in component:  # cima -> baixo; cada linha ja esta esq -> dir
            directions.extend(row["directions"])
            direction_candidates.extend(row["candidates"])
            centers = [
                item["rect"][0] + item["rect"][2] / 2.0
                for item in row["candidates"]
            ]
            gaps = np.diff(centers)
            if len(gaps) and np.mean(gaps):
                gap_variations.append(float(np.std(gaps) / np.mean(gaps)))

        if len(directions) < MIN_SEQUENCE_LENGTH:
            reason = f"sequencia curta ({len(directions)})"
        elif len(directions) > MAX_SEQUENCE_LENGTH:
            reason = f"sequencia longa ({len(directions)})"
        elif len(set(directions)) == 1:
            reason = "3+ direcoes identicas"
        else:
            gap_variation = float(np.mean(gap_variations)) if gap_variations else 1.0
            score = (len(set(directions)), -gap_variation, len(directions))
            valid_components.append((score, directions, direction_candidates))
            continue

        for candidate in direction_candidates:
            candidate["reason"] = reason

    if not valid_components:
        return {"directions": [], "mask": mask, "candidates": candidates}

    _, directions, direction_candidates = max(valid_components, key=lambda item: item[0])
    selected_ids = {id(candidate) for candidate in direction_candidates}
    for _, _, other_candidates in valid_components:
        for candidate in other_candidates:
            if id(candidate) not in selected_ids:
                candidate["reason"] = "outra linha candidata"

    for candidate in direction_candidates:
        candidate["accepted"] = True
        candidate["reason"] = "aceito"

    return {"directions": directions, "mask": mask, "candidates": candidates}


def detect_arrows(bgr_image):
    """Retorna lista de direcoes ('up'/'down'/'left'/'right') ordenada da
    esquerda para a direita, uma por seta detectada na imagem."""
    return analyze_arrow_candidates(bgr_image)["directions"]


def has_bright_text(bgr_image, min_pixels=20, brightness_threshold=180):
    """True se a imagem (ex: regiao do titulo) ainda tem pixels claros --
    usado para saber se o texto 'Memorize!' (branco/amarelo) ainda esta na tela."""
    gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    bright_pixels = np.count_nonzero(gray >= brightness_threshold)
    return int(bright_pixels) >= min_pixels


# A caixa de prompt ("Pressione qualquer tecla para comecar!/continuar" e
# "Jogo finalizado!") e UM UNICO painel verde escuro solido, em formato de
# faixa horizontal larga (bem mais largo que alto), com borda branca e
# texto branco brilhante dentro. Outros menus do jogo (estatisticas,
# habilidades) tem cor parecida mas aparecem como VARIOS paineis lado a
# lado, quadrados/altos, ocupando quase a tela toda -- entao exigimos um
# unico painel, largo, e que nao domine a tela quase inteira.
PROMPT_GREEN_LOWER = np.array([45, 60, 30])
PROMPT_GREEN_UPPER = np.array([75, 255, 160])
PROMPT_MIN_AREA_FRACTION = 0.05   # fracao minima da area da janela
PROMPT_MAX_AREA_FRACTION = 0.5    # painel de prompt nao domina a tela toda
PROMPT_MIN_ASPECT_RATIO = 1.8     # w/h -- faixa horizontal larga, nao quadrada
# fracao minima de pixels brilhantes DENTRO do miolo do painel (excluindo a
# borda) -- uma frase inteira de texto ocupa bem mais que uma borda fina
PROMPT_MIN_BRIGHT_FRACTION_INSIDE = 0.01


def is_prompt_screen(bgr_image):
    """True se a tela de prompt (unico painel verde solido, em faixa
    horizontal larga, com texto branco brilhante dentro) estiver visivel."""
    hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, PROMPT_GREEN_LOWER, PROMPT_GREEN_UPPER)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False

    image_area = bgr_image.shape[0] * bgr_image.shape[1]
    min_area = image_area * PROMPT_MIN_AREA_FRACTION

    # so conta paineis grandes o bastante para ser candidatos a prompt --
    # se houver mais de um (ex: varios paineis de um menu de estatisticas),
    # nao e a tela de prompt (que tem um unico painel isolado)
    big_contours = [c for c in contours if cv2.contourArea(c) >= min_area]
    if len(big_contours) != 1:
        return False

    largest = big_contours[0]
    area = cv2.contourArea(largest)
    if area > image_area * PROMPT_MAX_AREA_FRACTION:
        return False

    x, y, w, h = cv2.boundingRect(largest)
    if w / h < PROMPT_MIN_ASPECT_RATIO:
        return False

    panel_roi = bgr_image[y:y + h, x:x + w]

    # exclui a borda do painel (10% de margem de cada lado) para nao contar
    # a borda branca do proprio painel como se fosse texto interno
    margin_y, margin_x = max(1, h // 10), max(1, w // 10)
    inner = panel_roi[margin_y:h - margin_y, margin_x:w - margin_x]
    if inner.size == 0:
        return False

    gray = cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY)
    bright_pixels = np.count_nonzero(gray >= 180)
    return bright_pixels >= inner.shape[0] * inner.shape[1] * PROMPT_MIN_BRIGHT_FRACTION_INSIDE
