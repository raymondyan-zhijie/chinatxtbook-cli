"""SCR-SELECTED — Selected books panel (F2).

Summary and list of currently selected textbooks.
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, DataTable, Button

from chinatxtbook.utils.format import fmt_size


class SelectedScreen(ModalScreen):
    """SCR-SELECTED: View, review, and manage selected books.

    Shows total count, estimated size, and individual book status.
    """

    BINDINGS = [
        ("escape", "dismiss", "关闭"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="selected-screen"):
            yield Static("📋 已选教材", classes="modal-title")
            yield Static("", id="selected-summary", classes="summary-line")
            yield DataTable(id="selected-table")
            yield Static("", id="selected-empty", classes="modal-hint")
            with Horizontal():
                yield Button("开始下载 (F5)", variant="primary", id="selected-download")
                yield Button("关闭 (Esc)", variant="default", id="selected-close")

    def on_mount(self) -> None:
        table = self.query_one("#selected-table", DataTable)
        table.add_columns("", "教材名称", "分卷", "大小", "状态")
        table.cursor_type = "row"
        self._populate()

    def _populate(self) -> None:
        """Fill table from app's selected books."""
        app = self.app
        table = self.query_one("#selected-table", DataTable)
        table.clear()
        empty = self.query_one("#selected-empty", Static)
        summary = self.query_one("#selected-summary", Static)

        selected = getattr(app, 'selected_keys', set())
        if not selected:
            empty.update("未选择任何教材\n\n在左侧目录树中使用 Space 键选择")
            summary.update("")
            return

        empty.update("")
        # Gather book metadata from catalog data
        books = getattr(app, '_catalog_books', [])
        total_size = 0
        count = 0
        for b in books:
            if b.get('key') in selected:
                count += 1
                total_size += b.get('size', 0)
                sz_str = fmt_size(b.get('size', 0))
                parts_str = f"{b.get('part_count', '?')}卷"
                icon = "☑"
                table.add_row(icon, b.get('name', '?'), parts_str,
                              sz_str, "待下载")

        summary.update(f"共 {count} 册教材 │ 预估 {fmt_size(total_size)}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "selected-close":
            self.dismiss()
        elif event.button.id == "selected-download":
            self.dismiss()
            app = self.app
            if hasattr(app, 'action_confirm_download'):
                app.action_confirm_download()

    def action_dismiss(self) -> None:
        self.dismiss()
