"""Background download pipeline worker.

Handles clone→checkout→scan→merge→verify with real-time progress.
Handles both single PDFs and split PDFs. Output goes to OUTPUT_DIR.
"""

import asyncio
import os
import shutil
from pathlib import Path

from chinatxtbook.config import WORK_DIR, OUTPUT_DIR, DEFAULT_WORKERS, CHUNK_SIZE
from chinatxtbook.utils.format import fmt_size
from chinatxtbook.core.manifest import SplitManifest, SPLIT_RE


class PipelineWorker:
    """Runs clone→checkout→merge→verify pipeline with TUI progress."""

    STAGES = ["Preparing", "Downloading", "Merging", "Done"]

    def __init__(self, app):
        self.app = app

    async def run(self, selected_books: list) -> None:
        app = self.app
        total = len(selected_books)

        def _status(text):
            try:
                app.query_one("#status-bar").update_status(text)
            except Exception:
                pass

        def _progress(pct, stage, done=0):
            try:
                app.query_one("#status-bar").update_progress(
                    pct=pct, stage=stage, done=done, total=total)
            except Exception:
                pass

        _status(f"Processing {total} books...")
        _progress(5, "Preparing")

        git = app.git_client
        state = app.state

        # ── Ensure repo is ready ────────────────────────────
        if not git.is_repo_valid():
            _status("Cloning repository (may take a while)...")
            await asyncio.to_thread(git.clone, git.repo_url)
            if not git.is_repo_valid():
                _status("ERROR: Clone failed")
                app.pipeline_running = False
                return
            app._check_repo_status()

        _progress(10, "Preparing")

        # ── Collect unique directories from selected books ──
        dirs = set()
        for book in selected_books:
            path = book.get("path", "").rstrip("/")
            if path:
                dirs.add(path)

        if not dirs:
            _status("ERROR: No directories to download")
            app.pipeline_running = False
            return

        checkout_paths = sorted(d + "/" for d in dirs)
        state["selected_paths"] = checkout_paths

        # ── Download files via sparse-checkout ──────────────
        _status(f"Downloading {len(dirs)} directories...")
        _progress(20, "Downloading")

        try:
            await asyncio.to_thread(git.sparse_checkout, checkout_paths)
            branch = state.get("default_branch", "master")
            await asyncio.wait_for(
                asyncio.to_thread(git.checkout, branch),
                timeout=300,
            )
        except asyncio.TimeoutError:
            _status("ERROR: Download timed out (5 min) - check network")
            app.pipeline_running = False
            return
        except Exception as e:
            _status(f"ERROR: Download failed - {str(e)[:60]}")
            app.pipeline_running = False
            return

        _progress(50, "Downloading")

        # Verify files actually exist
        found = 0
        for book in selected_books:
            for part_info in book.get("parts", {}).values():
                fname = part_info[0] if isinstance(part_info, tuple) else part_info
                file_path = WORK_DIR / book["path"] / fname
                if file_path.exists():
                    found += 1
                    break

        if found == 0:
            _status("ERROR: No files downloaded - check network/Git LFS")
            app.pipeline_running = False
            return

        _status(f"Downloaded: {found}/{total} books have files")

        # ── Merge & copy to output ──────────────────────────
        _progress(60, "Merging")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        success = 0
        failed = 0
        skipped = 0

        for i, book in enumerate(selected_books):
            _progress(60 + int(35 * (i + 1) / total), "Merging", done=i + 1)
            _status(f"Processing [{i+1}/{total}]: {book['name'][:40]}")

            rel_dir = book["path"]
            base = book["name"]
            parts = book.get("parts", {})
            part_count = book.get("part_count", 1)

            # Check source files exist
            source_dir = WORK_DIR / rel_dir
            all_present = True
            for part_info in parts.values():
                fname = part_info[0] if isinstance(part_info, tuple) else part_info
                if not (source_dir / fname).exists():
                    all_present = False
                    break

            if not all_present:
                _status(f"  SKIP: source files missing for {base[:30]}")
                failed += 1
                continue

            # Output path
            out_dir = OUTPUT_DIR / rel_dir
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / base

            try:
                if part_count == 1:
                    # Single PDF: copy directly to output
                    fname = list(parts.values())[0]
                    fname = fname[0] if isinstance(fname, tuple) else fname
                    src = source_dir / fname
                    # Atomic copy
                    tmp = out_dir / f"{base}.tmp"
                    tmp.unlink(missing_ok=True)
                    shutil.copy2(src, tmp)
                    os.replace(str(tmp), str(out_file))
                    success += 1
                else:
                    # Split PDF: merge parts
                    await self._merge_parts(source_dir, out_dir, base, parts)
                    success += 1
            except Exception as e:
                _status(f"  FAIL: {base[:30]} - {str(e)[:40]}")
                failed += 1
                continue

        _progress(100, "Done", done=success + skipped)

        if failed:
            _status(f"DONE: {success} ok, {failed} failed → {OUTPUT_DIR.resolve()}")
        else:
            _status(f"COMPLETE: {success} books → {OUTPUT_DIR.resolve()}")

        app.pipeline_running = False

    async def _merge_parts(self, source_dir, out_dir, base, parts):
        """Merge split PDF parts into a single output file."""
        import hashlib
        out_file = out_dir / base
        tmp_file = out_dir / f"{base}.tmp"
        tmp_file.unlink(missing_ok=True)

        expected_size = 0
        for idx in sorted(parts):
            p = parts[idx]
            fname = p[0] if isinstance(p, tuple) else p
            expected_size += (source_dir / fname).stat().st_size

        stream_hash = hashlib.sha256()
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
                        stream_hash.update(chunk)
                        written += len(chunk)
                # Clean up source part if requested
            out_f.flush()
            os.fsync(out_f.fileno())

        if written != expected_size:
            tmp_file.unlink(missing_ok=True)
            raise IOError(f"Size mismatch: {written} vs {expected_size}")

        # Re-read verify
        r_hash = hashlib.sha256()
        with open(tmp_file, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                r_hash.update(chunk)

        if stream_hash.hexdigest() != r_hash.hexdigest():
            tmp_file.unlink(missing_ok=True)
            raise IOError("SHA256 mismatch - storage may be corrupt")

        os.replace(str(tmp_file), str(out_file))
