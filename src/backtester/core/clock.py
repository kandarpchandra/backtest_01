class SimulationClock:
    def __init__(self):
        self._current_time: float = 0.0

    @property
    def current_time(self) -> float:
        return self._current_time

    def advance(self, next_time: float) -> None:
        if next_time < self._current_time:
            raise ValueError(f"Cannot move time backwards: {self._current_time} -> {next_time}")
        self._current_time = next_time
