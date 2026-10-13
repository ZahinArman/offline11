"""
Logging and audit module for OFFLINE 11.
Records all warnings, decisions, emergency exceptions, shutdowns, and failures
with local timestamps for transparency and accountability.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from offline11.config import get_default_data_dir


@dataclass
class AuditEntry:
    timestamp: str
    event: str
    message: str
    details: Dict[str, Any]

    def to_line(self) -> str:
        """Formatted human-readable line."""
        dt_str = self.timestamp[:19].replace("T", " ")
        details_str = f" | {json.dumps(self.details)}" if self.details else ""
        return f"[{dt_str}] [{self.event.ljust(20)}] {self.message}{details_str}"


class AuditLogger:
    """Manages the persistent audit trail for curfew events."""

    def __init__(self, log_path: Optional[Path] = None, max_memory_entries: int = 500) -> None:
        if log_path is None:
            self.log_path = get_default_data_dir() / "audit.log"
        else:
            self.log_path = Path(log_path)
        self.max_memory_entries = max_memory_entries
        self._entries: List[AuditEntry] = []
        self._load_recent()

    def _load_recent(self) -> None:
        if not self.log_path.exists():
            return
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines[-self.max_memory_entries:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self._entries.append(
                        AuditEntry(
                            timestamp=data["timestamp"],
                            event=data["event"],
                            message=data["message"],
                            details=data.get("details", {}),
                        )
                    )
                except Exception:
                    continue
        except Exception:
            pass

    def log(self, event: str, message: str, details: Optional[Dict[str, Any]] = None, dt: Optional[datetime] = None) -> AuditEntry:
        """Records an audit event to disk and in-memory list."""
        if dt is None:
            dt = datetime.now().astimezone()
        timestamp = dt.isoformat()
        entry = AuditEntry(
            timestamp=timestamp,
            event=event,
            message=message,
            details=details or {},
        )
        self._entries.append(entry)
        if len(self._entries) > self.max_memory_entries:
            self._entries.pop(0)

        # Write to JSON-lines audit file
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry)) + "\n")
        except Exception as e:
            logging.error(f"Failed to write to audit log: {e}")

        # Also log to standard Python logger
        logging.info(f"AUDIT: [{event}] {message}")
        return entry

    def get_entries(self) -> List[AuditEntry]:
        """Returns in-memory audit entries."""
        return list(self._entries)

    def clear(self) -> None:
        """Clears all audit entries from memory and truncates log file."""
        self._entries.clear()
        try:
            if self.log_path.exists():
                with open(self.log_path, "w", encoding="utf-8") as f:
                    f.truncate(0)
            logging.info("Audit log cleared.")
        except Exception as e:
            logging.error(f"Failed to clear audit log: {e}")


def setup_app_logging(log_dir: Optional[Path] = None, debug: bool = False) -> logging.Logger:
    """Configures application logger writing to app.log and stdout."""
    if log_dir is None:
        log_dir = get_default_data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    root_logger = logging.getLogger("offline11")
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Avoid duplicate handlers if re-initialized
    if not root_logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        root_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
        root_logger.addHandler(console_handler)

    return root_logger
