"""Background download pipeline worker.

All steps logged to pipeline.log for diagnostics.
"""

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path

from chinatxtbook.config import WORK_DIR, OUTPUT_DIR, CHUNK_SIZE

# ── Diagnostic log ────────────────────────────────────────────

LOG_FILE = Path("pipeline.log")

def _log(msg: str):
    """Write to both console and log file."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class PipelineWorker:
    """Runs clone→checkout→merge→verify pipeline."""

    def __init__(self, app):
        self.app = app

    async def run(self, selected_books: list) -> None:
        app = self.app
        total = len(selected_books)
        _log(f"=== PIPELINE START: {total} books ===")

        def _status(text):
            _log(f"STATUS: {text}")
            try:
                app.query_one("#status-bar").update_status(text)
            except Exception as e:
                _log(f"  (status bar update failed: {e})")

        def _progress(pct, stage, done=0):
            try:
                app.query_one("#status-bar").update_progress(
                    pct=pct, stage=stage, done=done, total=total)
            except Exception:
                pass

        # ── Dump selection info ──────────────────────────────
        _log(f"selected_books count: {len(selected_books)}")
        for i, b in enumerate(selected_books[:5]):
            _log(f"  [{i}] key={b.get('key','?')} path={b.get('path','?')} "
                 f"name={b.get('name','?')[:40]} parts={b.get('part_count',0)}")
        _log(f"app.selected_keys count: {len(app.selected_keys)}")

        git = app.git_client
        state = app.state

        # ── Step 1: Ensure repo ──────────────────────────────
        _status(f"Step 1: Checking repo...")
        _log(f"Repo valid: {git.is_repo_valid()}")
        if not git.is_repo_valid():
            _status("Cloning repo...")
            _log("Starting clone...")
            await asyncio.to_thread(git.clone, git.repo_url)
            _log(f"After clone - repo valid: {git.is_repo_valid()}")
            if not git.is_repo_valid():
                _status("ERROR: Clone failed")
                app.pipeline_running = False
                return

        # ── Step 2: Collect directories ──────────────────────
        dirs = set()
        for book in selected_books:
            path = book.get("path", "").rstrip("/")
            if path:
                dirs.add(path)
        _log(f"Unique dirs to download: {len(dirs)}")
        for d in sorted(dirs):
            _log(f"  dir: {d}")

        if not dirs:
            _status("ERROR: No directories")
            app.pipeline_running = False
            return

        checkout_paths = sorted(d + "/" for d in dirs)
        _log(f"checkout_paths: {checkout_paths}")

        # ── Step 3: Download ─────────────────────────────────
        _status(f"Downloading {len(dirs)} dirs...")
        _progress(20, "Downloading")

        try:
            _log("Running sparse_checkout...")
            await asyncio.to_thread(git.sparse_checkout, checkout_paths)
            _log("sparse_checkout done, running checkout...")
            branch = state.get("default_branch", "master")
            _log(f"branch: {branch}")
            await asyncio.wait_for(
                asyncio.to_thread(git.checkout, branch),
                timeout=300,
            )
            _log("checkout done")
        except asyncio.TimeoutError:
            _log("TIMEOUT: checkout took >5 min")
            _status("ERROR: Download timed out")
            app.pipeline_running = False
            return
        except Exception as e:
            _log(f"ERROR during checkout: {e}")
            _status(f"ERROR: {str(e)[:60]}")
            app.pipeline_running = False
            return

        # ── Step 4: Verify files exist ───────────────────────
        _status("Verifying files...")
        found_books = 0
        missing_books = 0
        for book in selected_books:
            source_dir = WORK_DIR / book["path"]
            found_any = False
            for part_info in book.get("parts", {}).values():
                fname = part_info[0] if isinstance(part_info, tuple) else part_info
                fp = source_dir / fname
                exists = fp.exists()
                if exists:
                    found_any = True
            if found_any:
                found_books += 1
            else:
                missing_books += 1

        _log(f"File check: {found_books} books have files, {missing_books} missing")
        if found_books == 0:
            # Check what actually exists in workspace
            _log("No files found. Checking workspace content:")
            for d in dirs:
                p = WORK_DIR / d
                if p.exists():
                    contents = list(p.iterdir())[:5]
                    _log(f"  {d}/ exists, contents: {[c.name for c in contents]}")
                else:
                    _log(f"  {d}/ does NOT exist on disk")
            _status("ERROR: No files downloaded - check network")
            app.pipeline_running = False
            return

        _status(f"Found {found_books}/{total} books on disk")

        # ── Step 5: Merge/copy ───────────────────────────────
        _progress(60, "Merging")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        _log(f"Output dir: {OUTPUT_DIR.resolve()}")

        success = 0
        failed = 0

        for i, book in enumerate(selected_books):
            _progress(60 + int(35 * (i + 1) / total), "Merging", done=i + 1)

            rel_dir = book["path"]
            base = book["name"]
            parts = book.get("parts", {})
            part_count = book.get("part_count", 1)

            source_dir = WORK_DIR / rel_dir
            out_dir = OUTPUT_DIR / rel_dir
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / base

            # Check source
            all_present = True
            for part_info in parts.values():
                fname = part_info[0] if isinstance(part_info, tuple) else part_info
                if not (source_dir / fname).exists():
                    all_present = False
                    _log(f"  MISSING: {rel_dir}/{fname}")
                    break

            if not all_present:
                _log(f"  SKIP [{i+1}/{total}]: {base} - source files missing")
                failed += 1
                continue

            try:
                if part_count <= 1:
                    fname = list(parts.values())[0]
                    fname = fname[0] if isinstance(fname, tuple) else fname
                    src = source_dir / fname
                    tmp = out_dir / f"{base}.tmp"
                    tmp.unlink(missing_ok=True)
                    shutil.copy2(src, tmp)
                    os.replace(str(tmp), str(out_file))
                    sz = out_file.stat().st_size
                    _log(f"  OK [{i+1}/{total}]: {base} ({sz} bytes) → {out_file}")
                    success += 1
                else:
                    await self._merge_parts(source_dir, out_dir, base, parts)
                    sz = out_file.stat().st_size
                    _log(f"  OK [{i+1}/{total}]: {base} ({sz} bytes, {part_count} parts merged) → {out_file}")
                    success += 1
            except Exception as e:
                _log(f"  FAIL [{i+1}/{total}]: {base} - {e}")
                failed += 1

        _progress(100, "Done", done=success)
        _log(f"=== PIPELINE DONE: {success} ok, {failed} failed ===")

        if failed:
            _status(f"DONE: {success} ok, {failed} failed → {OUTPUT_DIR}")
        else:
            _status(f"COMPLETE: {success} books → {OUTPUT_DIR}")

        app.pipeline_running = False

    async def _merge_parts(self, source_dir, out_dir, base, parts):
        """Merge split PDF parts to output."""
        import hashlib
        out_file = out_dir / base
        tmp_file = out_dir / f"{base}.tmp"
        tmp_file.unlink(missing_ok=True)

        expected = 0
        for idx in sorted(parts):
            p = parts[idx]
            fname = p[0] if isinstance(p, tuple) else p
            expected += (source_dir / fname).stat().st_size

        h = hashlib.sha256()
        written = 0
        with open(tmp_file, "wb") as out_f:
            for idx in sorted(parts):
                p = parts[idx]
                fname = p[0] if isinstance(p, tuple) else p
                with open(source_dir / fname, "rb") as in_f:
                    while True:
                        chunk = in_f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        h.update(chunk)
                        written += len(chunk)
            out_f.flush()
            os.fsync(out_f.fileno())

        if written != expected:
            tmp_file.unlink(missing_ok=True)
            raise IOError(f"Size mismatch: {written} vs {expected}")

        r_hash = hashlib.sha256()
        with open(tmp_file, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                r_hash.update(chunk)

        if h.hexdigest() != r_hash.hexdigest():
            tmp_file.unlink(missing_ok=True)
            raise IOError("SHA256 mismatch")

        os.replace(str(tmp_file), str(out_file))
