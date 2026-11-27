"""
Configuration module for ShutCap.
Handles persistent settings, default times, validation, and serialization.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_default_data_dir() -> Path:
    """Returns the application data directory in %LOCALAPPDATA%\\ShutCap."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        path = Path(local_app_data) / "ShutCap"
    else:
        path = Path.home() / ".shutcap"
    path.mkdir(parents=True, exist_ok=True)
    return path


# (event key, config field, human label) in timeline order.
MILESTONES: List[Tuple[str, str, str]] = [
    ("warning_1", "warning_1_time", "First Warning"),
    ("warning_2", "warning_2_time", "Final Warning"),
    ("curfew", "curfew_time", "Curfew"),
    ("reminder_1", "grace_reminder_1_time", "Grace Reminder 1"),
    ("reminder_2", "grace_reminder_2_time", "Grace Reminder 2"),
    ("final_warning", "final_warning_time", "Last-Minute Warning"),
    ("shutdown", "shutdown_time", "Shutdown"),
]
MILESTONE_FIELDS: Dict[str, str] = {label: field for _, field, label in MILESTONES}

# Default minutes before the shutdown time for each milestone (used by first-run setup).
DEFAULT_MINUTES_BEFORE_SHUTDOWN: Dict[str, int] = {
    "warning_1_time": 45,
    "warning_2_time": 25,
    "curfew_time": 15,
    "grace_reminder_1_time": 10,
    "grace_reminder_2_time": 5,
    "final_warning_time": 1,
    "shutdown_time": 0,
}


class ScheduleError(ValueError):
    """A schedule problem that names the field the user must fix."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass
class Config:
    warning_1_time: str = "22:30"          # 10:30 PM: First warning
    warning_2_time: str = "22:50"          # 10:50 PM: Final warning before curfew
    curfew_time: str = "23:00"             # 11:00 PM: Curfew begins
    grace_reminder_1_time: str = "23:05"   # 11:05 PM: Reminder during countdown
    grace_reminder_2_time: str = "23:10"   # 11:10 PM: Reminder during countdown
    final_warning_time: str = "23:14"      # 11:14 PM: Final 1-minute warning
    shutdown_time: str = "23:15"           # 11:15 PM: Shutdown execution
    shutdown_grace_seconds: int = 60       # Delay in seconds for Windows shutdown command
    dry_run: bool = True                   # Safe testing mode: simulate shutdown without executing
    sound_enabled: bool = True             # Play audio chime on warnings and curfew
    desktop_reminder_window: bool = True   # Pop up modal/dialog reminder
    autostart: bool = False                # Auto-start on Windows login
    ntfy_enabled: bool = False             # Send Android push notifications via ntfy
    ntfy_topic: str = ""                   # ntfy topic name (e.g. shutcap_my_secret_code)
    ntfy_server: str = "https://ntfy.sh"   # ntfy server URL
    setup_complete: bool = False           # First-run setup finished

    @staticmethod
    def schedule_for_shutdown(shutdown_hhmm: str) -> Dict[str, str]:
        """Default milestone times (HH:MM) for a chosen shutdown time; wraps around midnight."""
        t = Config.parse_time_str(shutdown_hhmm)
        base = t.hour * 60 + t.minute
        result = {}
        for field_name, before in DEFAULT_MINUTES_BEFORE_SHUTDOWN.items():
            m = (base - before) % (24 * 60)
            result[field_name] = f"{m // 60:02d}:{m % 60:02d}"
        return result

    @staticmethod
    def derive_schedule(first_warning: str, curfew: str, shutdown: str) -> Dict[str, str]:
        """
        Full schedule from the three times that first-run setup shows.
        The last warning and the reminders are placed between them automatically:
        last warning 10 min before curfew, reminders 10, 5 and 1 min before shutdown,
        or spread evenly when the gaps are shorter. Raises ScheduleError(field, message).
        """
        def minutes(s: str) -> int:
            t = Config.parse_time_str(s)
            return t.hour * 60 + t.minute

        base = minutes(first_warning)
        c = (minutes(curfew) - base) % (24 * 60)
        o = (minutes(shutdown) - base) % (24 * 60)
        if c < 2:
            raise ScheduleError("curfew_time", "Must be 2 min after first warning.")
        if c >= o:
            raise ScheduleError("curfew_time", "Must be before Off.")
        if o - c < 4:
            raise ScheduleError("curfew_time", "Must be 4 min before Off.")
        w2 = c - 10 if c - 10 > 0 else c // 2
        if o - 10 > c:
            r1, r2, fw = o - 10, o - 5, o - 1
        else:
            g = (o - c) / 4
            r1, r2, fw = c + round(g), c + round(2 * g), c + round(3 * g)
        offsets = {
            "warning_1_time": 0, "warning_2_time": w2, "curfew_time": c,
            "grace_reminder_1_time": r1, "grace_reminder_2_time": r2,
            "final_warning_time": fw, "shutdown_time": o,
        }
        return {f: f"{((base + off) % 1440) // 60:02d}:{(base + off) % 60:02d}" for f, off in offsets.items()}

    @classmethod
    def parse_time_str(cls, time_str: str) -> time:
        """Parses 'HH:MM' string to a datetime.time object."""
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time format '{time_str}', expected 'HH:MM'.")
        hour = int(parts[0])
        minute = int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"Invalid time range '{time_str}'.")
        return time(hour=hour, minute=minute)

    def get_time_obj(self, field_name: str) -> time:
        """Returns the parsed datetime.time for a given time string field."""
        val = getattr(self, field_name)
        return self.parse_time_str(val)

    def milestone_offsets(self) -> List[Tuple[str, str, int]]:
        """
        Returns (key, label, minutes after Warning 1) for every milestone.
        Offsets wrap around midnight, so a schedule like 23:30 -> 00:15 is valid.
        """
        start = self.get_time_obj("warning_1_time")
        start_min = start.hour * 60 + start.minute
        result = []
        for key, field_name, label in MILESTONES:
            t = self.get_time_obj(field_name)
            result.append((key, label, (t.hour * 60 + t.minute - start_min) % (24 * 60)))
        return result

    def minutes_between(self, key_a: str, key_b: str) -> int:
        """Minutes from milestone key_a to milestone key_b (both from MILESTONES)."""
        offsets = {k: off for k, _, off in self.milestone_offsets()}
        return offsets[key_b] - offsets[key_a]

    def validate(self) -> None:
        """Validates that all schedule times are in order (the schedule may cross midnight)."""
        offsets = self.milestone_offsets()
        for (_, name_a, off_a), (_, name_b, off_b) in zip(offsets, offsets[1:]):
            if off_a >= off_b:
                fa = self.to_dict()[MILESTONE_FIELDS[name_a]]
                fb = self.to_dict()[MILESTONE_FIELDS[name_b]]
                raise ValueError(
                    f"Schedule sequence error: {name_a} ({fa}) must come before {name_b} ({fb})."
                )

        if self.shutdown_grace_seconds < 0 or self.shutdown_grace_seconds > 300:
            raise ValueError("shutdown_grace_seconds must be between 0 and 300 seconds.")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Config:
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class ConfigManager:
    """Manages loading and saving configuration to disk."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        if config_path is None:
            self.config_path = get_default_data_dir() / "config.json"
        else:
            self.config_path = Path(config_path)
        self.config: Config = self.load()

    def load(self) -> Config:
        """Loads configuration from JSON file or returns defaults if absent."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                config = Config.from_dict(data)
                config.validate()
                return config
            except Exception:
                # If config corrupted, fallback to defaults
                return Config()
        return Config()

    def save(self, config: Optional[Config] = None) -> None:
        """Saves current or provided configuration to disk atomically."""
        if config is not None:
            self.config = config
        self.config.validate()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.config_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, indent=4)
        temp_path.replace(self.config_path)
