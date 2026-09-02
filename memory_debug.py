"""Persist high-level memory detector evidence for post-run diagnosis."""

import json
from datetime import datetime
from pathlib import Path

import cv2

from arrow_detector import analyze_arrow_candidates


def save_memory_debug(frame, level, expected_count, sequence, sequence_limit):
    root = Path.home() / "Documents" / "DragonMine Perfect Recall" / "memory_debug"
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    base = root / f"level_{level:03d}_{stamp}"

    analysis = analyze_arrow_candidates(
        frame,
        sequence_limit,
        expected_count,
    )
    overlay = frame.copy()
    for candidate in analysis["candidates"]:
        x, y, width, height = candidate["rect"]
        color = (0, 220, 0) if candidate["accepted"] else (0, 0, 255)
        cv2.rectangle(overlay, (x, y), (x + width, y + height), color, 2)

    cv2.imwrite(str(base.with_suffix(".png")), frame)
    cv2.imwrite(str(base.with_name(base.name + "_overlay").with_suffix(".png")), overlay)
    base.with_suffix(".json").write_text(
        json.dumps(
            {
                "level": level,
                "expected": expected_count,
                "captured": len(sequence),
                "sequence": sequence,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return root
