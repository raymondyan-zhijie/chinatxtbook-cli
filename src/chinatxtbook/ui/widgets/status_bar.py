"""Status Bar Widget — bottom bar.

Shows: selection status | download progress | contextual hints.
"""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static

from chinatxtbook.utils.format import fmt_size


class StatusBarWidget(Container):
    """SCR-BROWSE bottom bar with contextual info."""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("📦 就绪 — Tab切换面板 Space选择教材", id="status-selection")
            yield Static("", id="status-progress")
            yield Static("←→展开目录 F5下载 F1帮助 Q退出", id="status-shortcuts")

    def update_info(self, selected_count: int = 0, estimated_size: int = 0) -> None:
        """Update selection display."""
        sel = self.query_one("#status-selection", Static)
        # Get disk space
        import shutil
        import os

        usage = shutil.disk_usage(os.getcwd())
        free_str = fmt_size(usage.free)
        if selected_count > 0:
            sel.update(
                f"☑ 已选 {selected_count} 册 │ 💾 {fmt_size(estimated_size)} │ "
                f"💿 {free_str} │ F2查看清单 F5下载"
            )
        else:
            from chinatxtbook.config import OUTPUT_DIR
            sel.update(f"📦 就绪 │ 💿 {free_str} │ 📁 {OUTPUT_DIR} │ Space选择 F5下载")

    def update_progress(
        self, pct: float = 0, stage: str = "", current: str = "", done: int = 0, total: int = 0
    ) -> None:
        """Show download progress."""
        prog = self.query_one("#status-progress", Static)
        if pct > 0:
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            prog.update(f"[{stage}] {bar} {pct:.0f}% ({done}/{total}) {current[:20]}")
        else:
            prog.update("")

    def update_status(self, text: str) -> None:
        """Simple status message."""
        sel = self.query_one("#status-selection", Static)
        sel.update(text)
