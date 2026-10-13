"""
Configuration module for OFFLINE 11.
Handles persistent settings, default times, validation, and serialization.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import time
from pathlib import Path
from typing import Any, Dict, Optional


def get_default_data_dir() -> Path:
    """Returns the application data directory in %LOCALAPPDATA%\\OFFLINE11."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        path = Path(local_app_data) / "OFFLINE11"
    else:
        path = Path.home() / ".offline11"
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    ntfy_topic: str = ""                   # ntfy topic name (e.g. offline11_my_secret_code)
    ntfy_server: str = "https://ntfy.sh"   # ntfy server URL

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

    def validate(self) -> None:
        """Validates that all schedule times are in sequential order."""
        t_w1 = self.get_time_obj("warning_1_time")
        t_w2 = self.get_time_obj("warning_2_time")
        t_curfew = self.get_time_obj("curfew_time")
        t_r1 = self.get_time_obj("grace_reminder_1_time")
        t_r2 = self.get_time_obj("grace_reminder_2_time")
        t_final = self.get_time_obj("final_warning_time")
        t_shutdown = self.get_time_obj("shutdown_time")

        times = [
            ("Warning 1", t_w1),
            ("Warning 2", t_w2),
            ("Curfew", t_curfew),
            ("Grace Reminder 1", t_r1),
            ("Grace Reminder 2", t_r2),
            ("Final Warning", t_final),
            ("Shutdown", t_shutdown),
        ]

        for i in range(len(times) - 1):
            name_a, time_a = times[i]
            name_b, time_b = times[i + 1]
            if time_a >= time_b:
                raise ValueError(
                    f"Schedule sequence error: {name_a} ({time_a.strftime('%H:%M')}) "
                    f"must be earlier than {name_b} ({time_b.strftime('%H:%M')})."
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
