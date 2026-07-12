"""Background download pipeline worker with full diagnostic logging."""

import asyncio
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from chinatxtbook.config import WORK_DIR, OUTPUT_DIR, CHUNK_SIZE

LOG_FILE = Path("pipeline.log")


def _log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception:
        pass


class PipelineWorker:

    def __init__(self, app):
        self.app = app

    def _find_status_bar(self):
        """Find the status bar widget across all screens."""
        for screen in reversed(self.app.screen_stack):
            try:
                return screen.query_one("#status-bar")
            except Exception:
                continue
        return None

    def _ui_status(self, text):
        _log(f"STATUS: {text}")
        bar = self._find_status_bar()
        if bar:
            bar.update_status(text)

    def _ui_progress(self, pct, stage, done=0):
        bar = self._find_status_bar()
        if bar:
            bar.update_progress(pct=pct, stage=stage, done=done)

    async def run(self, selected_books: list) -> None:
        app = self.app
        total = len(selected_books)
        _log(f"=== PIPELINE START: {total} books ===")

        for i, b in enumerate(selected_books[:5]):
            _log(f"  [{i}] key={b.get('key','?')} path={b.get('path','?')} "
                 f"name={b.get('name','?')[:40]} parts={b.get('part_count',0)}")
        _log(f"app.selected_keys count: {len(app.selected_keys)}")

        git = app.git_client
        state = app.state

        # Step 1: Ensure repo
        self._ui_status("Step 1: Checking repo...")
        _log(f"Repo valid: {git.is_repo_valid()}")
        if not git.is_repo_valid():
            self._ui_status("Cloning repo...")
            await asyncio.to_thread(git.clone, git.repo_url)
            if not git.is_repo_valid():
                self._ui_status("ERROR: Clone failed")
                app.pipeline_running = False
                return

        # Step 2: Collect dirs
        dirs = set()
        for book in selected_books:
            path = book.get("path", "").rstrip("/")
            if path:
                dirs.add(path)
        _log(f"Unique dirs: {len(dirs)}")
        for d in sorted(dirs):
            _log(f"  dir: {d}")

        if not dirs:
            self._ui_status("ERROR: No directories")
            app.pipeline_running = False
            return

        checkout_paths = sorted(d.rstrip("/") + "/" for d in dirs)

        # Step 3: Fetch + Checkout
        self._ui_status(f"Fetching updates...")
        self._ui_progress(10, "Downloading")
        branch = state.get("default_branch", "master")

        try:
            # Clean stale git lock files (from previous crashes)
            lock_file = WORK_DIR / ".git" / "index.lock"
            if lock_file.exists():
                _log(f"Removing stale lock: {lock_file}")
                lock_file.unlink(missing_ok=True)

            # Fetch all objects (critical for blobless clones behind slow networks)
            _log("git fetch origin...")
            self._ui_status("Fetching repo data...")
            self._ui_progress(10, "Downloading")
            await asyncio.wait_for(
                asyncio.to_thread(git.fetch, branch),
                timeout=120,
            )
            _log("git fetch done")

            # Disable sparse-checkout so index includes all files
            _log("disabling sparse-checkout...")
            git.run(["sparse-checkout", "disable"], retry=1)
            _log("sparse-checkout disabled")

            # Restore files individually
            self._ui_status(f"Restoring {len(dirs)} dirs...")
            self._ui_progress(20, "Downloading")

            # Collect all file paths to restore
            all_paths = []
            for book in selected_books:
                for pi in book.get("parts", {}).values():
                    fp = pi[1] if isinstance(pi, tuple) else pi
                    all_paths.append(fp)

            all_paths = list(set(all_paths))
            _log(f"Restoring {len(all_paths)} files...")

            # Use git show to extract files (works around checkout/restore
            # pathspec bug in blobless clones)
            failed_paths = []
            for i, git_path in enumerate(all_paths):
                # Clean stale locks
                lock = WORK_DIR / ".git" / "index.lock"
                lock.unlink(missing_ok=True)

                dest = WORK_DIR / git_path
                dest.parent.mkdir(parents=True, exist_ok=True)

                for attempt in range(3):
                    ok, out, err = git.run(
                        ["show", f"HEAD:{git_path}"],
                        allow_fetch=True, retry=1,
                    )
                    if ok:
                        # Write blob content to file
                        try:
                            dest.write_bytes(out.encode("utf-8") if isinstance(out, str) else out)
                        except Exception:
                            # Binary content - write raw bytes
                            r2 = subprocess.run(
                                ["git", "-C", str(WORK_DIR), "show", f"HEAD:{git_path}"],
                                capture_output=True,
                                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                            )
                            if r2.returncode == 0:
                                dest.write_bytes(r2.stdout)
                            else:
                                _log(f"show failed for {git_path}: {r2.stderr[:100]}")
                        break
                    _log(f"show {git_path[:50]} attempt {attempt+1}: {err[:80]}")
                    await asyncio.sleep(1)
                else:
                    failed_paths.append(git_path)

                pct = 20 + int(30 * (i + 1) / max(len(all_paths), 1))
                if i % 10 == 0:
                    self._ui_progress(min(pct, 50), "Downloading")

            if failed_paths:
                _log(f"Failed to download {len(failed_paths)} files")

            _log("restore done")
        except asyncio.TimeoutError:
            _log("TIMEOUT")
            self._ui_status("ERROR: Download timed out")
            app.pipeline_running = False
            return
        except Exception as e:
            _log(f"Download error: {e}")
            self._ui_status(f"ERROR: {str(e)[:60]}")
            app.pipeline_running = False
            return

        # Step 4: Verify files
        self._ui_status("Verifying files...")
        found = 0
        for book in selected_books:
            sd = WORK_DIR / book["path"]
            ok = False
            for pi in book.get("parts", {}).values():
                fn = pi[0] if isinstance(pi, tuple) else pi
                if (sd / fn).exists():
                    ok = True
                    break
            if ok:
                found += 1

        _log(f"Files on disk: {found}/{total}")
        if found == 0:
            for d in list(dirs)[:3]:
                p = WORK_DIR / d
                if p.exists():
                    _log(f"  {d}/ exists: {[c.name for c in list(p.iterdir())[:5]]}")
                else:
                    _log(f"  {d}/ MISSING")
            self._ui_status("ERROR: No files downloaded")
            app.pipeline_running = False
            return

        self._ui_status(f"Found {found}/{total} books on disk")
        self._ui_progress(50, "Merging")

        # Step 5: Merge/copy to output
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        _log(f"Output: {OUTPUT_DIR.resolve()}")
        ok_count = 0
        fail_count = 0

        for i, book in enumerate(selected_books):
            pct = 50 + int(45 * (i + 1) / total)
            self._ui_progress(pct, "Merging", done=i + 1)

            rd = book["path"]
            base = book["name"]
            parts = book.get("parts", {})
            pc = book.get("part_count", 1)

            sd = WORK_DIR / rd
            od = OUTPUT_DIR / rd
            od.mkdir(parents=True, exist_ok=True)
            of = od / base

            # Check source files
            missing = False
            for pi in parts.values():
                fn = pi[0] if isinstance(pi, tuple) else pi
                if not (sd / fn).exists():
                    missing = True
                    _log(f"  MISSING: {rd}/{fn}")
                    break
            if missing:
                fail_count += 1
                continue

            try:
                if pc <= 1:
                    fn = list(parts.values())[0]
                    fn = fn[0] if isinstance(fn, tuple) else fn
                    src = sd / fn
                    tmp = od / f"{base}.tmp"
                    tmp.unlink(missing_ok=True)
                    shutil.copy2(src, tmp)
                    os.replace(str(tmp), str(of))
                    _log(f"  OK [{i+1}/{total}]: {base} ({of.stat().st_size}B)")
                    ok_count += 1
                else:
                    await self._merge(sd, od, base, parts)
                    _log(f"  OK [{i+1}/{total}]: {base} merged ({of.stat().st_size}B)")
                    ok_count += 1
            except Exception as e:
                _log(f"  FAIL [{i+1}/{total}]: {base} - {e}")
                fail_count += 1

        self._ui_progress(100, "Done", done=ok_count)
        msg = f"COMPLETE: {ok_count} ok"
        if fail_count:
            msg += f", {fail_count} failed"
        msg += f" -> {OUTPUT_DIR}"
        self._ui_status(msg)
        _log(f"=== PIPELINE DONE: {ok_count} ok, {fail_count} failed ===")
        app.pipeline_running = False

    async def _merge(self, sd, od, base, parts):
        import hashlib
        of = od / base
        tf = od / f"{base}.tmp"
        tf.unlink(missing_ok=True)

        exp = sum((sd / (p[0] if isinstance(p, tuple) else p)).stat().st_size
                  for p in parts.values())

        h = hashlib.sha256()
        w = 0
        with open(tf, "wb") as out:
            for idx in sorted(parts):
                p = parts[idx]
                fn = p[0] if isinstance(p, tuple) else p
                with open(sd / fn, "rb") as inp:
                    while True:
                        c = inp.read(CHUNK_SIZE)
                        if not c:
                            break
                        out.write(c)
                        h.update(c)
                        w += len(c)
            out.flush()
            os.fsync(out.fileno())

        if w != exp:
            tf.unlink(missing_ok=True)
            raise IOError(f"Size mismatch: {w} vs {exp}")

        rh = hashlib.sha256()
        with open(tf, "rb") as f:
            while True:
                c = f.read(CHUNK_SIZE)
                if not c:
                    break
                rh.update(c)

        if h.hexdigest() != rh.hexdigest():
            tf.unlink(missing_ok=True)
            raise IOError("SHA256 mismatch")

        os.replace(str(tf), str(of))
