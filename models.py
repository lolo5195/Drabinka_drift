from dataclasses import dataclass, field

@dataclass(frozen=True)
class Driver:
    id: int     # Unique identifier for the driver
    name: str   # Name of the driver

@dataclass
class QualificationResult:
    driver: Driver
    run1: int = 0
    run2: int = 0

    @property
    def best(self) -> int:
        return max(self.run1, self.run2)
    @property
    def worst(self) -> int:
        return min(self.run1, self.run2)
    @property
    def is_zero(self) -> bool:
        return self.run1 == 0 and self.run2 == 0

@dataclass
class Match:
    match_id: str   # "T32_1".."T32_16", "T16_1".."T16_8",
                    # "T8_1".."T8_4", "T4_1", "T4_2", "FINAL", "PLAYOFF"
    slot_top: Driver | None = None # None = "-" (free spot)
    slot_bottom: Driver | None = None
    winner: Driver | None = None
    # Destination: (match_id, "top" | "bottom") or ("PODIUM", place).
    winner_goes_to: tuple[str, str] | None = None
    loser_goes_to: tuple[str, str] | None = None

@dataclass
class TournamentBracket:
    matches: dict[str, Match] = field(default_factory=dict)
    podium: dict[int, Driver | None] = field(
        default_factory=lambda: {1: None, 2: None, 3: None, 4: None}) 

