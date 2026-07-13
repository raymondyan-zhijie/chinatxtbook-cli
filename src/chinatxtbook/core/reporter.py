"""Status reporter and report generator extracted from v1.0.

Source: v1.0 lines 1530-1623.
"""

import os
from datetime import datetime

from chinatxtbook import VERSION
from chinatxtbook.config import WORK_DIR, REPORT_FILE
from chinatxtbook.core.state import groups_in_selection
from chinatxtbook.utils.format import fmt_size


class StatusReporter:
    """Display current task status. Source: v1.0 show_status() lines 1542-1573."""

    @staticmethod
    def show(state: dict):
        """Print status to console."""
        est, known = _estimate_selected_bytes(state)
        stages = [
            ("克隆", state.get("clone_done")),
            ("目录选择", state.get("selection_done")),
            ("文件检出", state.get("checkout_done")),
        ]
        groups = groups_in_selection(state)
        total_groups = len(state.get("groups", {}))
        fails = state.get("last_failures", {})

        print("═" * 58)
        print(f"  ChinaTextbook 任务状态 (v{VERSION})")
        print("═" * 58)
        print(f"  仓库源:       {state.get('repo_source') or '未选择'}")
        print(f"  默认分支:     {state.get('default_branch') or '未探测'}")
        for name, done in stages:
            mark = "✓ 完成" if done else "· 待执行"
            print(f"  {name}:{' ' * (12 - len(name) * 2)}{mark}")
        print(
            f"  选定路径:     {len(state.get('selected_paths', []))} 个"
            + (f"（预估 {fmt_size(est)}）" if known and est else "")
        )
        print(f"  含分卷目录:   {len(state.get('target_dirs', []))} 个")
        extra = total_groups - len(groups)
        print(
            f"  已合并组:     {len(groups)} 个 PDF（当前选择内）"
            + (f"，另有 {extra} 个历史选择的缓存记录" if extra > 0 else "")
        )
        print(f"  上次失败:     {len(fails)} 组")
        print(f"  上次运行:     {state.get('last_run') or 'N/A'}")
        print("═" * 58)

        for key, detail in list(fails.items())[:10]:
            print(f"    失败: {key}")
            print(f"          {str(detail)[:100]}")
        if len(fails) > 10:
            print(f"    ... 共 {len(fails)} 组，完整列表见 --report")


class ReportGenerator:
    """Generate Markdown report. Source: v1.0 generate_report() lines 1574-1613."""

    @staticmethod
    def generate(state: dict):
        """Generate atomically-written Markdown report."""
        est, known = _estimate_selected_bytes(state)
        groups = groups_in_selection(state)
        total_groups = len(state.get("groups", {}))
        fails = state.get("last_failures", {})

        lines = [
            "# ChinaTextbook 下载与合并报告",
            f"\n- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 工具版本: v{VERSION}",
            "\n## 概览\n",
            f"- 工作目录: `{WORK_DIR.resolve()}`",
            f"- 仓库源: `{state.get('repo_source', 'N/A')}`",
            f"- 分支: `{state.get('default_branch', 'N/A')}`",
            f"- 选定路径: {len(state.get('selected_paths', []))} 个"
            + (f"（预估 {fmt_size(est)}）" if known and est else ""),
            f"- 含分卷目录: {len(state.get('target_dirs', []))} 个",
            f"- 已合并组: {len(groups)} 个 PDF（当前选择内；历史缓存共 {total_groups} 条）",
            f"- 失败组: {len(fails)} 个",
            "\n## 选定路径\n",
        ]
        lines += [f"- `{p}`" for p in state.get("selected_paths", [])] or ["- (无)"]

        if fails:
            lines.append("\n## 失败详情\n")
            for key, detail in fails.items():
                lines.append(f"- `{key}`")
                lines.append(f"  - {detail}")

        if groups:
            lines.append("\n## 已合并 PDF（当前选择内）\n")
            for key in sorted(groups):
                g = groups[key]
                sha = (
                    f" sha256:{g['sha256'][:16]}…" if g.get("sha256") else ""
                )
                stale = " 【过期，待重新核对】" if g.get("stale") else ""
                lines.append(
                    f"- `{key}` ({fmt_size(g.get('size'))}{sha}){stale}"
                )

        lines.append(
            "\n> 说明: 校验为输出内容重读一致性校验（SHA256），"
            "保证本地合并写入无误；上游未提供基准哈希，"
            "无法验证分卷内容与上游一致，建议抽查打开若干大 PDF。"
        )

        # Atomic write: tmp → os.replace
        tmp = REPORT_FILE.with_suffix(REPORT_FILE.suffix + ".tmp")
        tmp.write_text("\n".join(lines) + "\n", "utf-8")
        os.replace(str(tmp), str(REPORT_FILE))


def _estimate_selected_bytes(state: dict) -> tuple:
    """Return (estimated_bytes, is_known). Source: v1.0 lines 630-643."""
    cache = state.get("size_cache") or {}
    if cache.get("truncated"):
        return 0, False
    dirs = cache.get("dirs") or {}
    total, known = 0, True
    for p in state.get("selected_paths", []):
        sz = dirs.get(p.rstrip("/"))
        if sz is None:
            known = False
        else:
            total += sz
    return total, known
