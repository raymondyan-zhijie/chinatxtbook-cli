"""Group evaluator extracted from v1.0 — THE SAFETY-CRITICAL DECISION ENGINE.

Decides merge/skip/error for each PDF split group by cross-referencing:
- Git tree manifest (authoritative)
- Workspace files (actual)
- Historical records (what we've seen before)

Source: v1.0 evaluate_group() lines 978-1098, collect_group_plans() lines 1298-1322.
Every condition and branch is preserved EXACTLY from v1.0.
"""

from pathlib import Path
from typing import Optional

from chinatxtbook.config import WORK_DIR
from chinatxtbook.core.manifest import SplitManifest
from chinatxtbook.core.merger import hash_file, InterruptedError


class GroupEvaluator:
    """Decision engine for split PDF groups.

    Cross-references Git manifest, workspace state, and historical records
    to determine the safe action for each group. All logic is preserved
    verbatim from v1.0 evaluate_group().
    """

    def __init__(self, work_dir: Path = WORK_DIR):
        self.work_dir = work_dir

    def evaluate(
        self,
        state: dict,
        rel_dir: str,
        base: str,
        present: Optional[dict],
        expected: Optional[dict],
        clean: bool = False,
        verify: bool = True,
    ) -> dict:
        """Evaluate one split group and decide action.

        Args:
            state: Full application state dict.
            rel_dir: Relative directory within workspace.
            base: Output PDF base name.
            present: {idx: [filenames]} from workspace scan.
            expected: {idx: filename} from git tree (None = outside manifest).
            clean: --clean mode (delete parts after verified merge).
            verify: Hash verification enabled.

        Returns:
            dict with keys: action ("merge"|"skip"|"error"),
            parts_map, restore, cleanup, detail.

        Source: v1.0 evaluate_group() lines 980-1098.
        """
        key = (Path(rel_dir) / base).as_posix()
        out_path = self.work_dir / rel_dir / base
        rec = (state.get("groups") or {}).get(key)
        strict = verify or clean

        # ── Duplicate part detection ──
        # Source: v1.0 lines 996-998
        dup = {i: n for i, n in (present or {}).items() if len(n) > 1}
        if dup:
            return {
                "action": "error",
                "detail": f"卷号重复（如 .1 与 .01 共存）: {dup}",
            }
        present_flat = {i: n[0] for i, n in (present or {}).items()}

        # ── Expected (Git manifest) present ──
        # Source: v1.0 lines 1002-1050
        if expected is not None:
            # Upstream duplicate detection (v1.0 L1003-1005)
            dup_exp = {i: n for i, n in expected.items() if isinstance(n, list)}
            if dup_exp:
                return {
                    "action": "error",
                    "detail": f"上游清单卷号重复: {dup_exp}",
                }

            exp_idx = sorted(expected)
            miss_seq = SplitManifest.missing_parts(exp_idx)
            if miss_seq:
                return {
                    "action": "error",
                    "detail": (
                        f"上游清单分卷不连续，缺少卷号 {miss_seq}"
                        "（属上游数据问题，可向上游反馈）"
                    ),
                }

            # Extra parts in workspace not in manifest (v1.0 L1011-1013)
            extra = [i for i in present_flat if i not in expected]
            if extra:
                import logging
                logging.warning(
                    f"  [{key}] 工作区存在 Git 清单之外的分卷 {extra}，已忽略"
                )

            # ── STALE RECORD HANDLING (v1.0 L1018-1040) ──
            # Stale records retain historical parts set; compare with
            # new manifest to detect upstream part deletion.
            if rec and rec.get("stale"):
                old_parts = set(rec.get("parts") or [])
                if not old_parts:
                    # Old record (v4.2/v4.3) has no parts field
                    if out_path.exists() and out_path.stat().st_size > 0:
                        return {
                            "action": "error",
                            "detail": (
                                "该组的旧版记录缺少分卷集合信息，上游变更后无法"
                                "确认是否删除了分卷；已保留现有 PDF。请人工核对"
                                "上游变更后删除输出文件重跑以强制重建"
                            ),
                        }
                else:
                    deleted = sorted(old_parts - set(exp_idx))
                    if deleted and out_path.exists() and out_path.stat().st_size > 0:
                        return {
                            "action": "error",
                            "detail": (
                                f"检测到上游删除了原有分卷 {deleted}（历史 "
                                f"{sorted(old_parts)} → 现 {exp_idx}），无法确认新"
                                "清单完整性；已保留现有 PDF，拒绝自动覆盖（如确认"
                                "上游变更合法，请删除输出文件后重跑以强制重建）"
                            ),
                        }
                    if deleted:
                        # Output already deleted by user (explicit rebuild)
                        import logging
                        logging.warning(
                            f"  [{key}] 上游已删除分卷 {deleted}，"
                            "本地无输出文件需保护，按新清单重建"
                        )

            # ── SINGLE-PART GROUP REJECTION (v1.0 L1041-1048) ──
            # A group with only .pdf.1 cannot prove no deleted subsequent parts.
            if exp_idx == [1]:
                return {
                    "action": "error",
                    "detail": (
                        "该组在 Git 清单中仅有 .pdf.1 单卷，无法证明不存在被删除的"
                        "后续分卷（上游未提供基准清单），已拒绝自动合并；"
                        "如确认该文件本身完整，请自行重命名使用或向上游反馈"
                    ),
                }

            parts_map = dict(expected)
            missing_local = [i for i in exp_idx if i not in present_flat]

        else:
            # ── NON-MANIFEST GROUP REJECTION (v1.0 L1051-1058) ──
            # Groups not in Git tree: cannot confirm completeness.
            return {
                "action": "error",
                "detail": (
                    "该分卷组不在 Git 树清单中，无法确认最后一卷是否完整，"
                    "为避免生成残缺 PDF 已拒绝自动合并（如确认分卷齐全，"
                    "请自行拼接或将文件移出工作区处理）"
                ),
            }

        # ── MISSING LOCAL PARTS (v1.0 L1060-1090) ──
        if missing_local:
            if out_path.exists() and out_path.stat().st_size > 0:
                sz = out_path.stat().st_size
                rec_ok = (
                    rec
                    and rec.get("status") == "ok"
                    and not rec.get("stale")
                    and rec.get("size") == sz
                )
                if rec_ok and rec.get("sha256"):
                    if strict:
                        try:
                            oh = hash_file(out_path).hexdigest()
                        except InterruptedError:
                            return {"action": "error", "detail": "用户中断"}
                        if oh == rec["sha256"]:
                            # Backfill parts for old records (v4.2/v4.3)
                            if not rec.get("parts"):
                                rec["parts"] = list(exp_idx)
                            # Cleanup residual parts if --clean
                            cleanup = (
                                [present_flat[i] for i in sorted(present_flat)]
                                if clean
                                else []
                            )
                            return {
                                "action": "skip",
                                "cleanup": cleanup,
                                "detail": "输出哈希与记录一致（分卷已清理）",
                            }
                        # Hash mismatch → output corrupted, restore and re-merge
                    else:
                        return {
                            "action": "skip",
                            "detail": (
                                "记录大小一致（--skip-verify 快速跳过，未做哈希核对）"
                            ),
                        }

            # No trusted record → restore missing parts and re-merge
            restore = [
                (Path(rel_dir) / parts_map[i]).as_posix() for i in missing_local
            ]
            return {
                "action": "merge",
                "parts_map": parts_map,
                "restore": restore,
                "detail": None,
            }

        # ── ALL PARTS PRESENT (v1.0 L1092-1098) ──
        # Strict mode: always enter merge for full hash comparison
        # Skip-verify mode: allow size-based fast skip with valid record
        if (
            not strict
            and rec
            and rec.get("status") == "ok"
            and not rec.get("stale")
            and out_path.exists()
            and out_path.stat().st_size == rec.get("size")
        ):
            return {
                "action": "skip",
                "detail": "记录大小一致（--skip-verify 快速跳过，未做哈希核对）",
            }
        return {
            "action": "merge",
            "parts_map": parts_map,
            "restore": [],
            "detail": None,
        }

    def collect_plans(
        self,
        state: dict,
        manifest: dict,
        clean: bool = False,
        verify: bool = True,
    ) -> tuple:
        """Evaluate all groups across selected directories.

        Returns (plans, errors, restores, skips, cleanups).
        Source: v1.0 collect_group_plans() lines 1298-1322.
        """
        from chinatxtbook.core.manifest import SplitManifest

        plans, errors, restores, skips, cleanups = [], {}, [], {}, []

        for rel_dir in state.get("target_dirs", []):
            present = SplitManifest.find_split_groups(self.work_dir / rel_dir)
            expected_dir = manifest.get(rel_dir)
            bases = set(present) | set(expected_dir or {})

            for base in sorted(bases):
                key = (Path(rel_dir) / base).as_posix()
                ev = self.evaluate(
                    state,
                    rel_dir,
                    base,
                    present.get(base),
                    (expected_dir or {}).get(base),
                    clean=clean,
                    verify=verify,
                )

                if ev["action"] == "error":
                    errors[key] = ev["detail"]
                elif ev["action"] == "skip":
                    skips[key] = ev["detail"]
                    if ev.get("cleanup"):
                        cleanups.append((rel_dir, ev["cleanup"]))
                else:  # merge
                    plans.append((key, rel_dir, base, ev["parts_map"]))
                    restores.extend(ev.get("restore") or [])

        return plans, errors, restores, skips, cleanups
