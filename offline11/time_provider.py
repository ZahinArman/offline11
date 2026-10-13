"""
Time provider module for OFFLINE 11.
Provides clock abstraction supporting both real local system time
and deterministic virtual time for accelerated testing.
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
    Can be stepped manually or run with an acceleration factor.
    """

    def __init__(self, initial_dt: Optional[datetime] = None, acceleration_factor: float = 1.0) -> None:
        if initial_dt is None:
            self._current_dt = datetime.now().astimezone()
        else:
            self._current_dt = initial_dt
        self.acceleration_factor = max(0.001, acceleration_factor)

    def now(self) -> datetime:
        return self._current_dt

    def set_time(self, new_dt: datetime) -> None:
        self._current_dt = new_dt

    def advance(self, seconds: float) -> None:
        self._current_dt += timedelta(seconds=seconds)

    def sleep(self, seconds: float) -> None:
        """Simulates sleep by advancing virtual time and waiting a scaled wall-clock interval."""
        self.advance(seconds)
        scaled_wait = seconds / self.acceleration_factor
        # Limit real wait to avoid stalling automated tests
        if scaled_wait > 0.05:
            scaled_wait = 0.05
        time.sleep(scaled_wait)
