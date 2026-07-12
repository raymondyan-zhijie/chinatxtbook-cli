"""Status Bar Widget — bottom bar.

Shows: selected count, estimated size, keyboard shortcuts hint.
Updates reactively via update_info().
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static

from chinatxtbook.utils.format import fmt_size


class StatusBarWidget(Container):
    """SCR-BROWSE bottom bar."""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("📦 就绪", id="status-selection")
            yield Static("", id="status-progress")
            yield Static(
                "/搜索 Space选择 F1帮助 F2已选 F5下载 F6任务 F8日志 F9更新 Q退出",
                id="status-shortcuts",
            )

    def update_info(self, selected_count: int = 0, estimated_size: int = 0) -> None:
        """Update selection display."""
        sel = self.query_one("#status-selection", Static)
        if selected_count > 0:
            sel.update(f"✅ 已选 {selected_count} 册 │ 💾 {fmt_size(estimated_size)}")
        else:
            sel.update("📦 就绪 — 使用 Space 键选择教材")

    def update_progress(self, pct: float = 0, current: str = "",
                        speed: float = 0, eta: float = 0,
                        done: int = 0, total: int = 0) -> None:
        """Show download progress."""
        prog = self.query_one("#status-progress", Static)
        parts = [f"⬇️ {pct:.0f}% ({done}/{total})"]
        if speed > 0:
            parts.append(f"{speed/1048576:.1f} MB/s")
        if eta > 0:
            m, s = divmod(int(eta), 60)
            parts.append(f"ETA {m}m{s}s")
        prog.update(" │ ".join(parts))
