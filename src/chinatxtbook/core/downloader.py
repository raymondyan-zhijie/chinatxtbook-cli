"""Download orchestrator extracted from v1.0.

Manages the download pipeline: clone, checkout, scan, merge, update.
Source: v1.0 lines 1100-1528.
"""

import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from chinatxtbook.config import WORK_DIR, DEFAULT_WORKERS, MAX_WORKERS
from chinatxtbook.core.git_client import GitClient
from chinatxtbook.core.evaluator import GroupEvaluator
from chinatxtbook.core.manifest import SplitManifest
from chinatxtbook.core.merger import PdfMerger, ProgressTracker
from chinatxtbook.core.state import StateManager
from chinatxtbook.utils.format import fmt_size, safe_error
from chinatxtbook.utils.platform import is_interrupted, clear_line


class DownloadOrchestrator:
    """Orchestrates the full download pipeline.

    Stages: clone → checkout → scan → merge → report.
    Source: v1.0 do_*() functions.
    """

    def __init__(
        self,
        git_client: GitClient,
        state_manager: StateManager,
        merger: Optional[PdfMerger] = None,
        evaluator: Optional[GroupEvaluator] = None,
        log_callback: Optional[Callable] = None,
    ):
        self.git = git_client
        self.state_mgr = state_manager
        self.merger = merger or PdfMerger(WORK_DIR)
        self.evaluator = evaluator or GroupEvaluator(WORK_DIR)
        self.log = log_callback or (lambda msg, level="INFO": None)

    # ── Clone ───────────────────────────────────────────────────

    def clone(self, state: dict, repo_url: str = None) -> bool:
        """Clone the repository (blobless). Source: v1.0 lines 1101-1130."""
        if not self.git.clone(repo_url):
            return False
        state["clone_done"] = True
        self.state_mgr.save(state)
        return True

    # ── Checkout ────────────────────────────────────────────────

    def checkout(self, state: dict, branch: str) -> bool:
        """Sparse-checkout selected paths. Source: v1.0 lines 1188-1247."""
        selected = state.get("selected_paths") or []
        if not selected:
            self.log("未选定下载路径，请先完成选择", "ERROR")
            return False

        # Validate all paths exist in git tree
        stale_paths = [p for p in selected if not self.git.path_exists_in_tree(p)]
        if stale_paths:
            self.log(
                f"以下选定路径在当前仓库树中不存在: {stale_paths}，请重新选择",
                "ERROR",
            )
            return False

        self.log("━━━ STEP 2: sparse-checkout 下载选定目录 ━━━", "STEP")

        if not self.git.sparse_checkout(selected):
            return False
        if not self.git.checkout(branch):
            return False

        # Post-checkout verification
        all_ok = True
        for p in selected:
            d = WORK_DIR / p.rstrip("/")
            tree_files = self.git.ls_tree(p, recursive=True)
            if not d.exists():
                self.log(
                    f"  {p.rstrip('/')}: 检出后目录不存在"
                    f"（Git 树中有 {len(tree_files)} 个文件）",
                    "ERROR",
                )
                all_ok = False
                continue

            files = [f for f in d.rglob("*") if f.is_file()]
            sz = sum(f.stat().st_size for f in files)
            if tree_files and not files:
                self.log(
                    f"  {p.rstrip('/')}: 目录为空但 Git 树中有"
                    f" {len(tree_files)} 个文件",
                    "ERROR",
                )
                all_ok = False
            else:
                self.log(
                    f"  {p.rstrip('/')}: {len(files)} 文件, {fmt_size(sz)}",
                    "OK" if len(files) == len(tree_files) else "WARN",
                )

        if not all_ok:
            return False

        state["checkout_done"] = True
        state["selection_fingerprint"] = StateManager.selection_fingerprint(selected)
        self.state_mgr.save(state)
        return True

    # ── Scan ──────────────────────────────────────────────────

    def scan(self, state: dict, force: bool = False) -> bool:
        """Scan for split PDF groups. Source: v1.0 lines 1255-1296."""
        if state.get("target_dirs") and not force:
            self.log(
                f"已知 {len(state['target_dirs'])} 个含分卷的目录", "OK"
            )
            return True

        self.log("━━━ STEP 3: 扫描分卷 PDF ━━━", "STEP")

        selected = state.get("selected_paths") or []

        # Build manifest from git tree (authoritative).
        # Fail-closed: if git tree can't be read, stop entirely.
        ls_out = "\n".join(
            self.git.ls_tree(p, recursive=True) for p in selected
        )
        manifest = SplitManifest.build_expected_manifest(ls_out, selected)
        if manifest is None:
            self.log(
                "无法读取 Git 树清单，为避免生成不完整 PDF，停止处理",
                "ERROR",
            )
            return False

        dirs = set(manifest.keys())

        # Scan workspace for anomalies (informational only)
        outside = set()
        for sel in selected:
            root = WORK_DIR / sel.rstrip("/")
            if not root.exists():
                continue
            for f in root.rglob("*"):
                if ".git" in f.parts:
                    continue
                from chinatxtbook.core.manifest import SPLIT_RE
                if f.is_file() and SPLIT_RE.match(f.name):
                    rel = f.parent.relative_to(WORK_DIR).as_posix()
                    if rel not in manifest:
                        outside.add(rel)
        if outside:
            self.log(
                f"发现 {len(outside)} 个目录含 Git 清单之外的本地分卷，"
                f"无法确认完整性，不会自动合并: {sorted(outside)}",
                "WARN",
            )

        state["target_dirs"] = sorted(dirs)
        self.state_mgr.save(state)

        if not dirs:
            self.log("未发现分卷文件", "WARN")
        else:
            n_groups = sum(len(v) for v in manifest.values())
            self.log(
                f"发现 {len(dirs)} 个目录（Git 清单 {n_groups} 组分卷）", "OK"
            )
        return True

    # ── Restore missing ─────────────────────────────────────────

    def restore_missing(self, restores: list) -> bool:
        """Restore missing split files from git. Source: v1.0 lines 1324-1337."""
        if not restores:
            return True
        return self.git.restore_files(restores)

    # ── Merge ──────────────────────────────────────────────────

    def merge(
        self,
        state: dict,
        manifest: dict,
        clean: bool = False,
        dry_run: bool = False,
        workers: int = DEFAULT_WORKERS,
        verify: bool = True,
        output_dir=None,
    ) -> bool:
        """Merge split PDFs with hash verification. Source: v1.0 lines 1339-1493."""
        self.log("━━━ STEP 4: 核对与合并 ━━━", "STEP")
        if not state.get("target_dirs"):
            self.log("无目标目录", "WARN")
            return True

        plans, errors, restores, skips, cleanups = self.evaluator.collect_plans(
            state, manifest, clean=clean, verify=verify
        )

        if dry_run:
            self.log(
                f"[DRY-RUN] 跳过 {len(skips)} 组 / 待合并 {len(plans)} 组 "
                f"/ 问题 {len(errors)} 组",
                "WARN",
            )
            for key, rel_dir, base, parts_map in plans:
                try:
                    sz = sum(
                        (WORK_DIR / rel_dir / n).stat().st_size
                        for n in parts_map.values()
                        if (WORK_DIR / rel_dir / n).exists()
                    )
                except OSError:
                    sz = 0
                need_restore = [
                    n for n in parts_map.values()
                    if not (WORK_DIR / rel_dir / n).exists()
                ]
                flag = f"  [需恢复 {len(need_restore)} 卷]" if need_restore else ""
                self.log(f"    {key}  ({len(parts_map)} 卷, {fmt_size(sz)}){flag}")
            for key, detail in errors.items():
                self.log(f"    [问题] {key}: {detail}", "ERROR")
            return True

        state["last_failures"] = dict(errors)
        for key, detail in errors.items():
            self.log(f"  [跳过-异常] {key}: {detail}", "ERROR")
        self.state_mgr.save(state)

        # Clean residual parts for hash-verified skipped groups
        if clean and cleanups:
            n_removed = 0
            for rel_dir, names in cleanups:
                for n in names:
                    p = WORK_DIR / rel_dir / n
                    if p.exists():
                        p.unlink(missing_ok=True)
                        n_removed += 1
            if n_removed:
                self.log(
                    f"已清理哈希核对通过的跳过组残余分卷 {n_removed} 个", "OK"
                )

        # Skip summary
        n_size = sum(1 for d in skips.values() if "快速跳过" in d)
        n_hash = len(skips) - n_size
        skip_parts = []
        if n_hash:
            skip_parts.append(f"哈希核对一致 {n_hash} 组")
        if n_size:
            skip_parts.append(f"按历史大小快速跳过（未哈希核对）{n_size} 组")
        skip_desc = "、".join(skip_parts)

        if not plans:
            msg = "核对完成: " + (skip_desc or "无待处理组") + "，无需合并"
            if errors:
                msg += f"；{len(errors)} 组存在问题"
            self.log(msg, "OK")
            return not errors

        if not self.restore_missing(restores):
            self.log("部分分卷恢复失败，相关组将报错", "ERROR")

        # Clean stale tmp files per-directory before launching thread pool
        for rel_dir in {rel_dir for _, rel_dir, _, _ in plans}:
            SplitManifest.clean_stale_tmp(WORK_DIR / rel_dir)

        # Calculate total size for progress
        total_bytes = 0
        for key, rel_dir, base, parts_map in plans:
            for n in parts_map.values():
                p = WORK_DIR / rel_dir / n
                if p.exists():
                    total_bytes += p.stat().st_size

        verify_label = (
            "ON" if verify
            else ("ON (--clean 强制)" if clean else "OFF")
        )
        self.log(
            f"并发线程: {workers} | 重读一致性校验: {verify_label} | "
            f"待合并 {len(plans)} 组: {fmt_size(total_bytes)}"
            + (f" | 预核对跳过 {len(skips)} 组" if skips else ""),
            "DATA",
        )

        progress = ProgressTracker(total_bytes)
        t0 = time.time()
        ok_count = fail_count = skip_count = 0
        done = 0

        def task(rel_dir, base, parts_map):
            status, size, digest, detail = self.merger.merge(
                rel_dir, base, parts_map,
                verify=verify, clean_intent=clean, progress=progress,
                output_dir=output_dir / rel_dir if output_dir else None,
            )
            if clean and (
                status == "ok" or (status == "skipped" and detail == "verified")
            ):
                for n in parts_map.values():
                    (WORK_DIR / rel_dir / n).unlink(missing_ok=True)
            return status, size, digest, detail

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(task, rel_dir, base, parts_map): (key, rel_dir, base, parts_map)
                for key, rel_dir, base, parts_map in plans
            }
            try:
                for future in as_completed(futures):
                    key, rel_dir, base, parts_map = futures[future]
                    done += 1
                    progress.clear()
                    try:
                        status, size, digest, detail = future.result()
                    except Exception as e:
                        status, size, digest, detail = "error", 0, None, f"未预期异常: {e}"

                    if status == "error":
                        fail_count += 1
                        state["last_failures"][key] = detail
                        self.log(
                            f"[{done}/{len(plans)}] {key} → 失败: {str(detail)[:160]}",
                            "ERROR",
                        )
                    else:
                        if digest is None:
                            prev = (state.get("groups") or {}).get(key) or {}
                            if prev.get("size") == size and not prev.get("stale"):
                                digest = prev.get("sha256")
                        state.setdefault("groups", {})[key] = {
                            "status": "ok",
                            "size": size,
                            "sha256": digest,
                            "parts": sorted(parts_map),
                            "at": datetime.now().isoformat(),
                        }
                        state["last_failures"].pop(key, None)
                        if status == "skipped":
                            skip_count += 1
                            self.log(
                                f"[{done}/{len(plans)}] {key} → 哈希核对一致，跳过"
                                + ("，已清理分卷" if clean else ""),
                                "OK",
                            )
                        else:
                            ok_count += 1
                            elapsed = time.time() - t0
                            speed = progress.done / elapsed if elapsed > 0 else 0
                            eta = (
                                (total_bytes - progress.done) / speed
                                if speed > 0 else 0
                            )
                            eta_str = (
                                f"{int(eta // 60)}m{int(eta % 60)}s"
                                if eta > 60 else f"{eta:.0f}s"
                            )
                            self.log(
                                f"[{done}/{len(plans)}] {key} → OK {fmt_size(size)} | "
                                f"{speed / 1048576:.1f} MB/s | ETA ~{eta_str}",
                                "OK",
                            )
                    self.state_mgr.save(state)
                    if is_interrupted():
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
            except KeyboardInterrupt:
                executor.shutdown(wait=False, cancel_futures=True)

        progress.clear()
        if is_interrupted():
            self.state_mgr.save(state)
            self.log("已中断，进度已保存。再次运行可从断点恢复。", "WARN")
            return False

        total_fail = fail_count + len(errors)
        self.log("━" * 55, "STEP")
        self.log(
            f"合并完成: {ok_count} 成功 / {total_fail} 失败 / "
            f"{skip_count + len(skips)} 跳过",
            "OK",
        )
        if total_fail:
            self.log("失败详情见 --status 或 --report", "WARN")
        return total_fail == 0

    # ── Update ─────────────────────────────────────────────────

    def update(self, state: dict, branch: str) -> bool:
        """Check for and apply upstream updates. Source: v1.0 lines 1495-1528."""
        self.log("━━━ UPDATE: 检查仓库更新 ━━━", "STEP")
        old = self.git.get_head_commit()

        if not self.git.fetch(branch):
            return False

        new = self.git.rev_parse(f"origin/{branch}")
        if old and new and old == new:
            self.log("已是最新，无需重新下载或重扫", "OK")
            return True

        if not self.git.merge_ff(branch):
            return False

        # Invalidate changed groups (stale marking)
        n = self.state_mgr.invalidate_by_diff(state, WORK_DIR, old, new)
        if n is None:
            self.log(
                "无法计算变更范围，已将全部组记录标记为过期",
                "WARN",
            )
        else:
            self.log(f"上游有更新: 标记 {n} 个组记录为过期", "OK")

        state["target_dirs"] = []
        state["size_cache"] = None
        state["checkout_done"] = False
        self.state_mgr.save(state)
        return True

    # ── Disk space ─────────────────────────────────────────────

    @staticmethod
    def check_disk_space(required_bytes: int, label: str = "") -> bool:
        """Check available disk space. Source: v1.0 lines 646-652."""
        usage = shutil.disk_usage(os.getcwd())
        if usage.free < required_bytes:
            return False
        return True

    @staticmethod
    def estimate_peak_space(est_bytes: int) -> int:
        """Peak disk usage formula. Source: v1.0 line 1180."""
        return int(est_bytes * 3.2) + 2 * 1024 ** 3
