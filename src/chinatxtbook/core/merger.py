"""PDF split-file merger extracted from v1.0.

Atomic write with streaming SHA256, flush+fsync, re-read verification,
and os.replace atomic rename. Source: v1.0 lines 839-976.
"""

import hashlib
import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from chinatxtbook.config import CHUNK_SIZE
from chinatxtbook.utils.platform import is_interrupted, clear_line, term_width

# ── File hashing ───────────────────────────────────────────────


class InterruptedError(Exception):
    """Raised when user interrupts during hashing/merging."""
    pass


def hash_file(path: Path, hasher=None) -> "hashlib._Hash":
    """Compute SHA256 hash of a file. Source: v1.0 lines 840-850."""
    h = hasher or hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            if is_interrupted():
                raise InterruptedError
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h


def hash_parts(dir_path: Path, parts_map: dict) -> str:
    """Compute SHA256 of concatenated split files in index order.
    Source: v1.0 lines 852-857.
    """
    h = hashlib.sha256()
    for idx in sorted(parts_map):
        hash_file(dir_path / parts_map[idx], h)
    return h.hexdigest()


# ── Progress tracking ──────────────────────────────────────────


class ProgressTracker:
    """Aggregate progress for multi-threaded merging.
    Source: v1.0 lines 860-887.
    """

    def __init__(self, total_bytes: int):
        self.total = max(total_bytes, 1)
        self.done = 0
        self._last: dict = {}
        self._lock = threading.Lock()
        self._last_print = 0.0

    def cb(self, written: int, expected: int, key: str):
        with self._lock:
            prev = self._last.get(key, 0)
            self.done += written - prev
            self._last[key] = written
            now = time.time()
            if now - self._last_print < 0.3:
                return
            self._last_print = now
            pct = min(100, self.done * 100 // self.total)
            name = os.path.basename(key)
            name = name[:32] + "…" if len(name) > 33 else name
            line = (
                f"  合并中 {pct:3d}% "
                f"({self.done / 1048576:.1f}/{self.total / 1048576:.1f} MB) "
                f"当前: {name}"
            )
            sys_term_width = max(20, term_width() - 1)
            import sys
            sys.stdout.write("\r" + line[:sys_term_width])
            sys.stdout.flush()

    def clear(self):
        with self._lock:
            clear_line()


# ── Core merge logic ───────────────────────────────────────────


class PdfMerger:
    """Atomic split-PDF merger with SHA256 integrity verification.

    Source: v1.0 merge_one_file() lines 889-976.
    """

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir

    def merge(
        self,
        rel_dir: str,
        base: str,
        parts_map: dict,
        verify: bool = True,
        clean_intent: bool = False,
        progress: Optional[ProgressTracker] = None,
        output_dir: Optional[Path] = None,
    ) -> tuple:
        """Merge split PDF parts into a single file.

        Args:
            rel_dir: Relative directory within work_dir for SOURCE files.
            base: Output PDF filename (e.g. "语文一年级上册.pdf").
            parts_map: {idx: filename} dict of split parts.
            verify: Enable hash verification.
            clean_intent: Force re-read verification (--clean).
            progress: Optional progress tracker.
            output_dir: If set, output goes here instead of work_dir/rel_dir.

        Returns:
            (status, size, sha256_or_none, detail)
              status: "ok" | "skipped" | "error"

        Source: v1.0 lines 890-976.
        """
        source_dir = self.work_dir / rel_dir
        out_dir = output_dir or source_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / base
        tmp_path = out_dir / f"{base}.tmp"
        key = str(out_path)
        written = 0
        must_verify = verify or clean_intent

        try:
            # ── Existing output check: hash verification ──
            # Source: v1.0 lines 908-915
            if out_path.exists() and out_path.stat().st_size > 0 and must_verify:
                expected = sum(
                    (source_dir / parts_map[i]).stat().st_size for i in parts_map
                )
                if out_path.stat().st_size == expected:
                    ph = hash_parts(source_dir, parts_map)
                    oh = hash_file(out_path).hexdigest()
                    if ph == oh:
                        return "skipped", out_path.stat().st_size, oh, "verified"

            # ── Atomic merge: tmp → flush → fsync → verify → replace ──
            # Source: v1.0 lines 920-967
            tmp_path.unlink(missing_ok=True)
            stream_hasher = hashlib.sha256()
            expected_size = 0

            with open(tmp_path, "wb") as out_f:
                for idx in sorted(parts_map):
                    if is_interrupted():
                        raise InterruptedError
                    part_path = source_dir / parts_map[idx]
                    expected_size += part_path.stat().st_size
                    with open(part_path, "rb") as in_f:
                        while True:
                            if is_interrupted():
                                raise InterruptedError
                            chunk = in_f.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            stream_hasher.update(chunk)
                            written += len(chunk)
                            if progress:
                                progress.cb(written, expected_size, key)
                out_f.flush()
                os.fsync(out_f.fileno())

            # ── Size check ──
            actual_size = tmp_path.stat().st_size
            if actual_size != expected_size:
                tmp_path.unlink(missing_ok=True)
                return (
                    "error",
                    actual_size,
                    None,
                    f"大小不匹配: 写入 {actual_size} vs 预期 {expected_size}",
                )

            digest = stream_hasher.hexdigest()

            # ── Re-read consistency verification ──
            if must_verify:
                disk_digest = hash_file(tmp_path).hexdigest()
                if digest != disk_digest:
                    tmp_path.unlink(missing_ok=True)
                    return (
                        "error",
                        actual_size,
                        None,
                        "重读一致性校验失败（存储层可能异常）",
                    )

            # ── Atomic replace ──
            os.replace(str(tmp_path), str(out_path))

            # ── POSIX: fsync parent directory ──
            if os.name == "posix":
                try:
                    dfd = os.open(str(out_dir), os.O_RDONLY)
                    try:
                        os.fsync(dfd)
                    finally:
                        os.close(dfd)
                except OSError:
                    pass

            return "ok", actual_size, digest, None

        except InterruptedError:
            tmp_path.unlink(missing_ok=True)
            return "error", written, None, "用户中断"
        except FileNotFoundError as e:
            tmp_path.unlink(missing_ok=True)
            return "error", 0, None, f"分卷文件缺失: {getattr(e, 'filename', e)}"
        except OSError as e:
            tmp_path.unlink(missing_ok=True)
            return "error", 0, None, f"IO 错误: {e}"
