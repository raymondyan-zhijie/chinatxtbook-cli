"""Platform utilities extracted from v1.0.

Terminal setup, VT color support, interrupt handling.
Source: v1.0 lines 130-171, 194-200.
"""

import os
import shutil
import signal
import sys

# ── Interrupt handling ──────────────────────────────────────────
_INTERRUPTED = False


def _on_sigint(signum, frame):
    """Source: v1.0 lines 132-138."""
    global _INTERRUPTED
    if _INTERRUPTED:
        print("\n[EXIT] 再次收到 Ctrl+C，强制退出")
        os._exit(130)
    _INTERRUPTED = True
    print("\n[PAUSE] 收到 Ctrl+C，正在完成当前块并保存状态...（再按一次强制退出）")


def setup_interrupt_handler():
    """Register SIGINT handler. Source: v1.0 line 140."""
    signal.signal(signal.SIGINT, _on_sigint)


def is_interrupted() -> bool:
    """Check if interrupt has been requested."""
    return _INTERRUPTED


# ── Console setup ──────────────────────────────────────────────

USE_COLOR = True

_C = {
    "INFO": "\033[0m",
    "OK": "\033[32m",
    "WARN": "\033[33m",
    "ERROR": "\033[31m",
    "STEP": "\033[36m",
    "DATA": "\033[90m",
    "BOLD": "\033[1m",
}


def setup_console():
    """Initialize console for VT color and UTF-8 output.
    Source: v1.0 lines 149-171.
    """
    global USE_COLOR
    if sys.platform == "win32":
        os.system("chcp 65001 >nul 2>&1")
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            handle = k32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if k32.GetConsoleMode(handle, ctypes.byref(mode)):
                if not k32.SetConsoleMode(handle, mode.value | 0x0004):
                    USE_COLOR = False
            else:
                USE_COLOR = False
        except Exception:
            USE_COLOR = False
    if not sys.stdout.isatty():
        USE_COLOR = False


def term_width() -> int:
    """Get terminal width. Source: v1.0 lines 194-198."""
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


def clear_line():
    """Clear the current terminal line. Source: v1.0 lines 200-203."""
    w = max(20, term_width() - 1)
    sys.stdout.write("\r" + " " * w + "\r")
    sys.stdout.flush()
