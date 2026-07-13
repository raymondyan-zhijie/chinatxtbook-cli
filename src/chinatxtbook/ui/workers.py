"""Background download pipeline worker with full diagnostic logging."""

import asyncio
import os
import subprocess
from datetime import datetime
from pathlib import Path

from chinatxtbook.config import WORK_DIR, OUTPUT_DIR, CHUNK_SIZE

LOG_FILE = Path("pipeline.log")


def _log(msg: str):
    """Write to pipeline log file only (no stdout pollution in TUI)."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
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
        self.app._log_buffer.append(("STEP", text))
        bar = self._find_status_bar()
        if bar:
            bar.update_status(text)

    def _ui_progress(self, pct, stage, done=0):
        bar = self._find_status_bar()
        if bar:
            bar.update_progress(pct=pct, stage=stage, done=done)
        # Update _tasks for SCR-TASKS
        if self.app._tasks:
            self.app._tasks[0]["stage"] = stage
            self.app._tasks[0]["progress"] = int(pct)

    async def run(self, selected_books: list) -> None:
        app = self.app
        total = len(selected_books)
        _log(f"=== PIPELINE START: {total} books ===")

        # Populate _tasks for SCR-TASKS screen
        app._tasks = [
            {
                "id": f"tsk-{total}",
                "name": f"下载 {total} 册教材",
                "stage": "Preparing",
                "progress": 0,
                "status": "Running",
            }
        ]

        for i, b in enumerate(selected_books[:5]):
            _log(
                f"  [{i}] key={b.get('key','?')} path={b.get('path','?')} "
                f"name={b.get('name','?')[:40]} parts={b.get('part_count',0)}"
            )
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

        sorted(d.rstrip("/") + "/" for d in dirs)

        # Step 3: Fetch + Checkout
        self._ui_status("Fetching updates...")
        self._ui_progress(10, "Downloading")
        branch = state.get("default_branch", "master")

        try:
            # N-6: Only delete index.lock if no other git process is active
            lock_file = WORK_DIR / ".git" / "index.lock"
            if lock_file.exists():
                import subprocess as _sp

                r = _sp.run(
                    ["git", "-C", str(WORK_DIR), "status", "--short"],
                    capture_output=True,
                    timeout=10,
                    env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                )
                if r.returncode != 0 and b"index.lock" in (r.stderr or b""):
                    _log("index.lock held by another process — cannot acquire")
                    self._ui_status("ERROR: Git index locked by another process")
                    app.pipeline_running = False
                    return
                _log("Removing stale index.lock")
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
                dest = WORK_DIR / git_path
                dest.parent.mkdir(parents=True, exist_ok=True)

                for attempt in range(3):
                    # Use raw subprocess (not git.run) to avoid text encoding
                    # which corrupts binary PDF data
                    r = subprocess.run(
                        ["git", "-C", str(WORK_DIR), "show", f"HEAD:{git_path}"],
                        capture_output=True,
                        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                    )
                    if r.returncode == 0:
                        dest.write_bytes(r.stdout)
                        break
                    from chinatxtbook.utils.format import safe_error

                    _log(f"show {git_path[:50]} attempt {attempt+1}: {safe_error(r.stderr, 80)}")
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
        # ── Safety: run GroupEvaluator before merging ──────────
        self._ui_status("Safety check...")
        self._ui_progress(45, "Verifying")

        from chinatxtbook.core.manifest import SplitManifest, SPLIT_RE

        # Build manifest from git tree (fail-closed)
        all_files = []
        for d in dirs:
            result = git.ls_tree(d, recursive=True)
            if result is None:
                _log(f"FAIL-CLOSED: cannot read git tree for {d}")
                self._ui_status("ERROR: Git tree read failed (fail-closed)")
                app.pipeline_running = False
                return
            all_files.extend(result)
        manifest = SplitManifest.build_expected_manifest("\n".join(all_files), list(dirs))
        if manifest is None:
            _log("FAIL-CLOSED: manifest build failed")
            self._ui_status("ERROR: Manifest build failed (fail-closed)")
            app.pipeline_running = False
            return

        # Run evaluator on each book
        from chinatxtbook.core.evaluator import GroupEvaluator

        evaluator = GroupEvaluator(WORK_DIR)
        prefiltered = []
        for book in selected_books:
            rd = book["path"]
            base = book["name"]
            pc = book.get("part_count", 1)

            # F-05: Single PDFs (not split parts) bypass evaluator
            # Manifest only tracks split files (.pdf.N); single PDFs
            # are not split volumes and don't need completeness checks
            is_single_pdf = pc == 1
            if is_single_pdf:
                # Check it's genuinely a single PDF, not a lone .pdf.1
                parts_dict = book.get("parts", {})
                if parts_dict:
                    fname = list(parts_dict.values())[0]
                    fname = fname[0] if isinstance(fname, tuple) else fname
                    from chinatxtbook.core.manifest import SPLIT_RE

                    if not SPLIT_RE.match(fname):
                        # It's a real single PDF — safe to include directly
                        _log(f"  SINGLE PDF: {base} — copying directly")
                        prefiltered.append(book)
                        continue

            # Get present files from workspace
            present = SplitManifest.find_split_groups(WORK_DIR / rd)
            expected = (manifest.get(rd) or {}).get(base)
            ev = evaluator.evaluate(app.state, rd, base, present.get(base), expected, verify=True)
            action = ev.get("action", "merge")
            if action == "error":
                _log(f"  SAFETY SKIP: {base} — {ev.get('detail','')[:80]}")
            elif action == "skip":
                _log(f"  ALREADY VERIFIED: {base}")
                # Still include — will be skipped in merge
                prefiltered.append(book)
            else:
                prefiltered.append(book)

        if not prefiltered:
            self._ui_status("All books skipped or blocked by safety checks")
            app.pipeline_running = False
            return

        # F-07: Disk space check before merge
        from chinatxtbook.core.downloader import DownloadOrchestrator

        est_size = sum(b.get("size", 0) for b in prefiltered)
        peak = DownloadOrchestrator.estimate_peak_space(est_size)
        import shutil as _shutil

        usage = _shutil.disk_usage(
            str(OUTPUT_DIR.resolve()) if OUTPUT_DIR.exists() else str(OUTPUT_DIR.parent.resolve())
        )
        if usage.free < peak:
            _log(f"DISK FULL: need {peak//(1024**3)}GB, have {usage.free//(1024**3)}GB")
            self._ui_status(f"ERROR: Disk full — need {peak//(1024**3)}GB free")
            app.pipeline_running = False
            return

        _log(f"Safety check: {len(prefiltered)}/{total} books passed")
        selected_books = prefiltered
        total = len(selected_books)

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

            # F-17/M-3: Validate output path with PathPolicy
            from chinatxtbook.utils.paths import PathPolicy

            safe_of = PathPolicy.safe_write_path(OUTPUT_DIR, f"{rd}/{base}")
            if safe_of is None:
                _log(f"  PATH REJECTED OUTPUT: {rd}/{base}")
                fail_count += 1
                continue
            sd = WORK_DIR / rd
            # Validate restore path too
            for pi in parts.values():
                fn = pi[0] if isinstance(pi, tuple) else pi
                safe_src = PathPolicy.resolve_within(WORK_DIR, f"{rd}/{fn}")
                if safe_src is None:
                    _log(f"  PATH REJECTED SOURCE: {rd}/{fn}")
                    fail_count += 1
                    continue
            # Write directly to validated safe path
            of = safe_of
            od = safe_of.parent

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
                # F-04: Persist group record to state for breakpoint resume
                # and upstream deletion detection (A4/A6)
                group_key = f"{rd}/{base}"
                if pc <= 1:
                    fn = list(parts.values())[0]
                    fn = fn[0] if isinstance(fn, tuple) else fn
                    src = sd / fn
                    tmp = od / f"{base}.tmp"
                    tmp.unlink(missing_ok=True)
                    # Copy with SHA256 verification
                    import hashlib as _hashlib

                    h = _hashlib.sha256()
                    with open(src, "rb") as fin, open(tmp, "wb") as fout:
                        while True:
                            chunk = fin.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            fout.write(chunk)
                            h.update(chunk)
                        fout.flush()
                        os.fsync(fout.fileno())
                    h2 = _hashlib.sha256()
                    with open(tmp, "rb") as f:
                        while True:
                            chunk = f.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            h2.update(chunk)
                    if h.hexdigest() != h2.hexdigest():
                        tmp.unlink(missing_ok=True)
                        raise IOError("SHA256 mismatch")
                    os.replace(str(tmp), str(of))
                    _log(
                        f"  OK [{i+1}/{total}]: {base} ({of.stat().st_size}B, sha:{h.hexdigest()[:12]})"
                    )
                    ok_count += 1
                    # F-04: Persist group record to state
                    app.state.setdefault("groups", {})[group_key] = {
                        "status": "ok",
                        "size": of.stat().st_size,
                        "sha256": h.hexdigest(),
                        "parts": sorted(parts),
                        "at": datetime.now().isoformat(),
                    }
                else:
                    merged_sha = await self._merge(sd, od, base, parts)
                    _log(
                        f"  OK [{i+1}/{total}]: {base} merged ({of.stat().st_size}B, sha:{merged_sha[:12]})"
                    )
                    ok_count += 1
                    # F-04: Persist group record to state
                    app.state.setdefault("groups", {})[group_key] = {
                        "status": "ok",
                        "size": of.stat().st_size,
                        "sha256": merged_sha,
                        "parts": sorted(parts),
                        "at": datetime.now().isoformat(),
                    }
            except Exception as e:
                _log(f"  FAIL [{i+1}/{total}]: {base} - {e}")
                fail_count += 1

            # F-04: Save state after each book for breakpoint resume
            try:
                app.state_mgr.save(app.state)
            except Exception:
                pass

        self._ui_progress(100, "Done", done=ok_count)
        msg = f"COMPLETE: {ok_count} ok"
        if fail_count:
            msg += f", {fail_count} failed"
        msg += f" -> {OUTPUT_DIR}"
        self._ui_status(msg)
        app._log_buffer.append(("OK", msg))
        _log(f"=== PIPELINE DONE: {ok_count} ok, {fail_count} failed ===")
        app._tasks = []
        app.pipeline_running = False

    async def _merge(self, sd, od, base, parts):
        import hashlib

        of = od / base
        tf = od / f"{base}.tmp"
        tf.unlink(missing_ok=True)

        exp = sum(
            (sd / (p[0] if isinstance(p, tuple) else p)).stat().st_size for p in parts.values()
        )

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
        return h.hexdigest()  # N-4: return computed SHA256
