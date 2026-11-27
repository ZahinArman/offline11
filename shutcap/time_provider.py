"""
Time provider module for ShutCap.
Provides clock abstraction supporting both real local system time
and virtual time for tests and accelerated simulation.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional


class TimeProvider(ABC):
    """Abstract base class for time operations."""

    @abstractmethod
    def now(self) -> datetime:
        """Returns the current datetime with local timezone."""
        raise NotImplementedError

    @abstractmethod
    def sleep(self, seconds: float) -> None:
        """Pauses execution for the given duration."""
        raise NotImplementedError


class RealTimeProvider(TimeProvider):
    """Uses the real Windows system clock and local timezone."""

    def now(self) -> datetime:
        return datetime.now().astimezone()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class VirtualTimeProvider(TimeProvider):
    """
    Virtual clock for testing and simulation.

    - Stepped mode (running=False, used by unit tests): time only moves via set_time()/advance().
    - Running mode (running=True): time flows at acceleration_factor x real time.
    """

    def __init__(
        self,
        initial_dt: Optional[datetime] = None,
        acceleration_factor: float = 1.0,
        running: bool = False,
    ) -> None:
        self._base_dt = initial_dt if initial_dt is not None else datetime.now().astimezone()
        self._base_mono = time.monotonic()
        self.acceleration_factor = max(0.001, acceleration_factor)
        self.running = running

    def now(self) -> datetime:
        if not self.running:
            return self._base_dt
        elapsed = (time.monotonic() - self._base_mono) * self.acceleration_factor
        return self._base_dt + timedelta(seconds=elapsed)

    def set_time(self, new_dt: datetime) -> None:
        self._base_dt = new_dt
        self._base_mono = time.monotonic()

    def advance(self, seconds: float) -> None:
        self.set_time(self.now() + timedelta(seconds=seconds))

    def sleep(self, seconds: float) -> None:
        """Simulates sleep by advancing virtual time and waiting a short scaled wall-clock interval."""
        self.advance(seconds)
        time.sleep(min(0.05, seconds / self.acceleration_factor))
