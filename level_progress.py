"""Round-based level accounting for the memory minigame."""

from dataclasses import dataclass


DEFAULT_SEQUENCE_LIMIT = 128


def expected_arrows_for_level(level):
    """Observed DragonMine rule: 3 arrows, then +1 every two levels."""
    return 3 + (level - 1) // 2


def sequence_limit_for_target(target_level):
    """Capacity required through the confirmation round after the target.

    Observed DragonMine progression starts with three arrows and adds one
    every two levels. Two extra slots keep the sanity limit tolerant to small
    progression changes while still rejecting implausibly large HUD reads.
    """
    if target_level is None:
        return DEFAULT_SEQUENCE_LIMIT
    confirmation_level = target_level + 1
    expected_arrows = expected_arrows_for_level(confirmation_level)
    return expected_arrows + 2


def wrong_direction_for(expected_direction):
    """Return a deterministic direction that cannot match the expected one."""
    return {
        "up": "down",
        "down": "up",
        "left": "right",
        "right": "left",
    }[expected_direction]


@dataclass(frozen=True)
class LevelUpdate:
    current_level: int
    completed_level: int | None
    target_reached: bool


class LevelProgress:
    """Count only levels whose success is confirmed by the next round."""

    def __init__(self, target_level=None):
        self.target_level = target_level
        self.run_completed = 0
        self.current_level = 0
        self.best_completed = 0

    def begin_round(self):
        completed_level = None
        if self.current_level:
            self.run_completed = self.current_level
            self.best_completed = max(self.best_completed, self.run_completed)
            completed_level = self.run_completed

        target_reached = (
            self.target_level is not None
            and self.run_completed >= self.target_level
        )
        if target_reached:
            return LevelUpdate(0, completed_level, True)

        self.current_level = self.run_completed + 1
        return LevelUpdate(self.current_level, completed_level, False)

    def reset_run(self):
        self.run_completed = 0
        self.current_level = 0
