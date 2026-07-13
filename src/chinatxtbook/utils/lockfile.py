"""Single-instance lock extracted from v1.0.

Atomic O_EXCL lock file with PID tracking and stale-lock reclamation.
Source: v1.0 lines 222-294.
"""

import atexit
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


def _pid_alive(pid: int) -> bool:
    """Check if a process with the given PID is still running.
    Source: v1.0 lines 226-246.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        except Exception:
            return True  # Conservative: assume alive if we can't check
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


class InstanceLock:
    """Single-instance lock using O_EXCL file creation.

    Prevents concurrent runs in the same directory. Stale locks from
    crashed processes are reclaimed atomically via os.rename().

    Source: v1.0 lines 222-294 (acquire_lock, release_lock, _pid_alive).
    """

    def __init__(self, lock_file: Path = Path("china_textbook.lock")):
        self.lock_file = lock_file
        self._acquired = False

    def acquire(self) -> bool:
        """Attempt to acquire the lock. Returns True on success.

        Source: v1.0 lines 259-294.
        """
        for _ in range(2):
            try:
                fd = os.open(
                    str(self.lock_file),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(
                        {"pid": os.getpid(), "started": datetime.now().isoformat()},
                        f,
                    )
                self._acquired = True
                atexit.register(self.release)
                return True
            except FileExistsError:
                try:
                    info = json.loads(self.lock_file.read_text("utf-8"))
                    pid = int(info.get("pid", -1))
                    info.get("started", "?")
                except Exception:
                    pid, _started = -1, "?"

                if _pid_alive(pid):
                    return False

                # Stale lock: reclaim atomically via rename to avoid races
                reclaim = self.lock_file.with_name(f"{self.lock_file.name}.stale.{os.getpid()}")
                try:
                    os.rename(str(self.lock_file), str(reclaim))
                    reclaim.unlink(missing_ok=True)
                except OSError:
                    # Another process claimed it first; retry O_EXCL
                    time.sleep(0.05)
        return False

    def release(self):
        """Release the lock. Safe to call multiple times.
        Source: v1.0 lines 247-257.
        """
        if not self._acquired:
            return
        try:
            info = json.loads(self.lock_file.read_text("utf-8"))
            if int(info.get("pid", -1)) == os.getpid():
                self.lock_file.unlink(missing_ok=True)
        except Exception:
            pass
        self._acquired = False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("Another instance is running")
        return self

    def __exit__(self, *args):
        self.release()
