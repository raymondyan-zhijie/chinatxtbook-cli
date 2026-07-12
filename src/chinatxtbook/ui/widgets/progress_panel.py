"""Progress Panel Widget — download/merge progress overlay."""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static, ProgressBar


class ProgressPanelWidget(Container):
    """Overlay panel showing download and merge progress.

    Shows: overall progress bar, current file, speed, ETA.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        self.display = False
        with Vertical(id="progress-overlay"):
            yield Static("下载进度", classes="modal-title")
            yield ProgressBar(id="overall-progress", total=100, show_eta=False)
            yield Static("准备中...", id="progress-current-file", classes="current-file")
            yield Static("", id="progress-speed-eta", classes="speed-eta")

    def show(self) -> None:
        """Show the progress overlay."""
        self.display = True
        self.add_class("visible")

    def hide(self) -> None:
        """Hide the progress overlay."""
        self.display = False
        self.remove_class("visible")

    def update_progress(
        self,
        overall_pct: float,
        current_file: str = "",
        speed_bytes: float = 0,
        eta_seconds: float = 0,
        done: int = 0,
        total: int = 0,
    ) -> None:
        """Update all progress indicators."""
        bar = self.query_one("#overall-progress", ProgressBar)
        bar.update(progress=overall_pct)

        current = self.query_one("#progress-current-file", Static)
        current.update(f"当前: {current_file}" if current_file else f"{done}/{total} 完成")

        speed_eta = self.query_one("#progress-speed-eta", Static)
        parts = []
        if speed_bytes > 0:
            parts.append(f"{speed_bytes / 1048576:.1f} MB/s")
        if eta_seconds > 0:
            m, s = divmod(int(eta_seconds), 60)
            parts.append(f"ETA {m}m{s}s")
        speed_eta.update(" │ ".join(parts))
