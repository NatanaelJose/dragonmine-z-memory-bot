"""Offline checks for normalized rhythm-lane capture geometry."""

import numpy as np

from rhythm_capture import crop_lane, lane_bounds, lane_capture_rect


def main():
    frame = np.zeros((1017, 1920, 3), dtype=np.uint8)
    bounds = lane_bounds(frame.shape)
    lane = crop_lane(frame)

    print("Limites da pista em 1920x1017:", bounds)
    print("Formato recortado:", lane.shape)

    assert bounds == (77, 386, 1843, 641)
    assert lane.shape == (255, 1766, 3)
    assert lane_capture_rect((0, 23, 1920, 1009)) == (77, 406, 1766, 253)

    small = np.zeros((480, 854, 3), dtype=np.uint8)
    small_lane = crop_lane(small)
    assert small_lane.shape[0] > 0 and small_lane.shape[1] > 0

    print("OK: regiao normalizada cobre a pista em resolucoes diferentes")


if __name__ == "__main__":
    main()
