"""Logging utilities extracted from v1.0.

Thread-safe logging with file rotation and URL redaction.
Source: v1.0 lines 173-221.
"""

import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from chinatxtbook.utils.format import redact_url


class Logger:
    """Thread-safe logger with console output and file rotation.

    Source: v1.0 log() function (L182-192) + rotate_log() (L173-179).
    """

    def __init__(
        self,
        log_file: Path,
        max_bytes: int = 5 * 1024 * 1024,
        use_color: bool = True,
        callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.log_file = log_file
        self.max_bytes = max_bytes
        self.use_color = use_color
        self._callback = callback  # For TUI log screen
        self._lock = threading.Lock()

        # Color codes (same as v1.0 _C dict)
        self._colors = {
            "INFO": "\033[0m",
            "OK": "\033[32m",
            "WARN": "\033[33m",
            "ERROR": "\033[31m",
            "STEP": "\033[36m",
            "DATA": "\033[90m",
            "BOLD": "\033[1m",
        }

    def _rotate_if_needed(self):
        """Rotate log file if it exceeds max_bytes. Source: v1.0 lines 173-179."""
        try:
            if self.log_file.exists() and self.log_file.stat().st_size > self.max_bytes:
                backup = self.log_file.with_name(self.log_file.name + ".1")
                backup.unlink(missing_ok=True)
                self.log_file.replace(backup)
        except Exception:
            pass

    def log(self, msg: str, level: str = "INFO"):
        """Thread-safe log entry. Source: v1.0 lines 182-192."""
        ts = datetime.now().strftime("%H:%M:%S")
        c = self._colors.get(level, "") if self.use_color else ""
        r = "\033[0m" if c else ""
        with self._lock:
            print(f"{c}[{ts}] {msg}{r}")
            try:
                self._rotate_if_needed()
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(f"[{ts}] [{level}] {redact_url(msg)}\n")
            except OSError:
                pass
        # Notify TUI callback if registered
        if self._callback:
            try:
                self._callback(level, msg)
            except Exception:
                pass

    # Convenience methods
    def info(self, msg: str):
        self.log(msg, "INFO")

    def ok(self, msg: str):
        self.log(msg, "OK")

    def warn(self, msg: str):
        self.log(msg, "WARN")

    def error(self, msg: str):
        self.log(msg, "ERROR")

    def step(self, msg: str):
        self.log(msg, "STEP")

    def data(self, msg: str):
        self.log(msg, "DATA")
