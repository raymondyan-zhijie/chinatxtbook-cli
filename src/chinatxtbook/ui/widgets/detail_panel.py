"""Detail Panel Widget — right panel.

Shows metadata for the currently focused book.
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static

from chinatxtbook.utils.format import fmt_size


class DetailPanelWidget(Container):
    """SCR-BROWSE right panel: focused book details."""

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-content"):
            yield Static("📄 文件详情", id="detail-title")
            yield Static("选择一个教材以查看详情", id="detail-name")
            yield Static("", id="detail-meta")

    def on_mount(self) -> None:
        """Watch for focus changes via app state polling."""
        self.set_interval(0.5, self._refresh_from_app)

    def _refresh_from_app(self) -> None:
        """Read focused_book from app and update display."""
        app = self.app
        if not hasattr(app, "focused_book") or not app.focused_book:
            return

        book = app.focused_book
        name_w = self.query_one("#detail-name", Static)
        meta_w = self.query_one("#detail-meta", Static)

        name_w.update(book.get("name", book.get("base", "N/A")))

        lines = [
            f"📐 分卷: {book.get('part_count', '?')} 卷",
            f"💾 总大小: {fmt_size(book.get('size', 0))}",
            f"📁 路径: {book.get('path', book.get('key', 'N/A'))}",
        ]

        if book.get("sha256"):
            lines.append(f"🔐 SHA256: {book['sha256'][:16]}…")

        # Show part breakdown
        parts = book.get("parts", {})
        if isinstance(parts, dict) and parts:
            lines.append("")
            lines.append("━━ 分卷详情 ━━")
            for idx in sorted(parts):
                p = parts[idx]
                p_name = p[0] if isinstance(p, tuple) else p
                lines.append(f"  卷 {idx}: {p_name}")

        meta_w.update("\n".join(lines))
