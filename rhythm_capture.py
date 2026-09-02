"""Timed diagnostic recorder for the DragonMine Z rhythm minigame.

The first implementation deliberately records evidence instead of pressing
keys. The resulting lane video and per-frame timestamps let us measure travel
direction, note speed, hit lines, and sustain duration from real gameplay.
"""

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import mss

from capture import grab_window
from window import focus_game_window, get_window_rect


LANE_REGION = {
    "left": 0.04,
    "top": 0.38,
    "right": 0.96,
    "bottom": 0.63,
}
DEFAULT_DURATION = 12.0
DEFAULT_FPS = 60.0
VIDEO_SCALE = 0.5


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def lane_bounds(frame_shape, region=LANE_REGION):
    """Return a normalized rhythm-lane rectangle as integer pixel bounds."""
    height, width = frame_shape[:2]
    left = max(0, min(width - 1, round(width * region["left"])))
    top = max(0, min(height - 1, round(height * region["top"])))
    right = max(left + 1, min(width, round(width * region["right"])))
    bottom = max(top + 1, min(height, round(height * region["bottom"])))
    return left, top, right, bottom


def crop_lane(frame, region=LANE_REGION):
    left, top, right, bottom = lane_bounds(frame.shape, region)
    return frame[top:bottom, left:right]


def lane_capture_rect(window_rect, region=LANE_REGION):
    """Convert the normalized lane into an absolute MSS capture rectangle."""
    window_left, window_top, width, height = window_rect
    left, top, right, bottom = lane_bounds((height, width, 3), region)
    return window_left + left, window_top + top, right - left, bottom - top


def default_capture_root():
    return Path.home() / "Documents" / "DragonMine Perfect Recall" / "rhythm_captures"


def wait_for_window():
    last_warning = 0.0
    while True:
        rect = get_window_rect()
        if rect is not None:
            return rect
        now = time.time()
        if now - last_warning >= 3:
            log("RHYTHM_CAPTURE:WAITING_FOR_WINDOW Abra a janela DragonMine.")
            last_warning = now
        time.sleep(0.25)


def record_rhythm_session(duration=DEFAULT_DURATION, target_fps=DEFAULT_FPS, output_root=None):
    if not 3 <= duration <= 60:
        raise ValueError("Capture duration must be between 3 and 60 seconds.")
    if not 15 <= target_fps <= 120:
        raise ValueError("Capture FPS must be between 15 and 120.")

    window_rect = wait_for_window()
    output_root = Path(output_root) if output_root else default_capture_root()
    session_name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    session_dir = output_root / session_name
    session_dir.mkdir(parents=True, exist_ok=False)

    focus_game_window()
    for remaining in (3, 2, 1):
        log(f"RHYTHM_CAPTURE:COUNTDOWN Gravacao em {remaining}...")
        time.sleep(1)

    video_path = session_dir / "lane.avi"
    reference_path = session_dir / "reference.png"
    timestamps_path = session_dir / "timestamps.csv"
    metadata_path = session_dir / "metadata.json"

    writer = None
    frame_count = 0
    last_progress_second = -1
    initial_window_size = [window_rect[2], window_rect[3]]
    lane_rect = lane_capture_rect(window_rect)
    lane_size = [lane_rect[2], lane_rect[3]]
    video_size = [round(lane_size[0] * VIDEO_SCALE), round(lane_size[1] * VIDEO_SCALE)]
    started_at = None
    recording_ended_at = None

    try:
        with mss.MSS() as sct, timestamps_path.open("w", newline="", encoding="utf-8") as timestamps_file:
            timestamps = csv.writer(timestamps_file)
            timestamps.writerow(["frame", "elapsed_ms"])

            # Prepare the relatively expensive full-frame reference and video
            # encoder before starting the timing clock. The high-frequency loop
            # captures only the narrow lane instead of the entire 1080p window.
            reference_frame = grab_window(sct, window_rect)
            cv2.imwrite(str(reference_path), reference_frame)
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            writer = cv2.VideoWriter(str(video_path), fourcc, target_fps, tuple(video_size))
            if not writer.isOpened():
                raise RuntimeError("OpenCV could not create the rhythm capture video.")

            # The first MJPG write loads codec internals and can cost hundreds
            # of milliseconds. Keep one marked pre-roll frame outside the
            # timing clock so gameplay sampling starts warm.
            warmup_lane = grab_window(sct, lane_rect)
            warmup_lane = cv2.resize(warmup_lane, tuple(video_size), interpolation=cv2.INTER_AREA)
            writer.write(warmup_lane)
            timestamps.writerow([0, -1])

            log(f"RHYTHM_CAPTURE:RECORDING Capturando pista por {duration:.0f}s a {target_fps:.0f} FPS...")
            started_at = time.perf_counter()

            while True:
                scheduled_at = started_at + frame_count / target_fps
                delay = scheduled_at - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)

                capture_started_at = time.perf_counter()
                if capture_started_at - started_at >= duration:
                    break

                lane = grab_window(sct, lane_rect)
                captured_at = (capture_started_at + time.perf_counter()) / 2
                elapsed = captured_at - started_at
                lane = cv2.resize(lane, tuple(video_size), interpolation=cv2.INTER_AREA)
                writer.write(lane)
                timestamps.writerow([frame_count + 1, round(elapsed * 1000, 3)])
                frame_count += 1

                progress_second = int(elapsed)
                if progress_second != last_progress_second:
                    last_progress_second = progress_second
                    log(f"RHYTHM_CAPTURE:PROGRESS {min(progress_second + 1, int(duration))}/{int(duration)}s")
            recording_ended_at = time.perf_counter()
    finally:
        if writer is not None:
            writer.release()

    elapsed_total = recording_ended_at - started_at
    metadata = {
        "formatVersion": 1,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "durationRequestedSeconds": duration,
        "durationActualSeconds": round(elapsed_total, 6),
        "targetFps": target_fps,
        "averageFps": round(frame_count / elapsed_total, 3) if elapsed_total else 0,
        "frameCount": frame_count,
        "videoFrameCount": frame_count + 1,
        "warmupFrames": 1,
        "windowSize": initial_window_size,
        "laneSize": lane_size,
        "videoSize": video_size,
        "videoScale": VIDEO_SCALE,
        "laneRegionNormalized": LANE_REGION,
        "video": video_path.name,
        "timestamps": timestamps_path.name,
        "referenceFrame": reference_path.name,
        "codec": "MJPG",
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    log(f"RHYTHM_CAPTURE:SAVED Captura salva em: {session_dir}")
    log(f"RHYTHM_CAPTURE:SUMMARY {frame_count} frames, media de {metadata['averageFps']:.1f} FPS")
    return session_dir
