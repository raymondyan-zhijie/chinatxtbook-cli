"""OVL-CONFIRM - Download confirmation overlay (F5).

Shows selected books list (scrollable), summary, and confirmation.
Arrow keys navigate buttons, Enter confirms, Esc cancels.
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button, RichLog

from chinatxtbook.utils.format import fmt_size


class ConfirmOverlay(ModalScreen):
    """OVL-CONFIRM: Scrollable book list + download summary + confirmation."""

    BINDINGS = [
        ("escape", "dismiss", "取消"),
        ("up,down", "focus_next_button", "", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-overlay"):
            yield Static("⬇️ 下载确认", classes="modal-title")
            yield Static("", id="confirm-summary", classes="modal-content")
            yield RichLog(id="confirm-book-list", highlight=True, markup=False, max_lines=12)
            yield Static("", id="confirm-disk", classes="modal-content")
            with Horizontal():
                yield Button("确认下载 (Enter)", variant="primary", id="confirm-yes")
                yield Button("取消 (Esc)", variant="default", id="confirm-no")

    def on_mount(self) -> None:
        app = self.app
        selected: set = getattr(app, "selected_keys", set())
        books = getattr(app, "_catalog_books", [])

        total_books = len(selected)
        total_files = 0
        total_size = 0
        selected_books = [b for b in books if b.get("key") in selected]

        for b in selected_books:
            total_files += b.get("part_count", 1)
            total_size += b.get("size", 0)

        # Disk check
        import shutil
        import os

        usage = shutil.disk_usage(os.getcwd())
        free_gb = usage.free / (1024**3)
        peak = int(total_size * 3.2) + 2 * 1024**3

        from chinatxtbook.config import OUTPUT_DIR

        summary = self.query_one("#confirm-summary", Static)
        summary.update(
            f"教材数: {total_books} 册 | 源文件: {total_files} 个 | "
            f"预估: {fmt_size(total_size)} | 峰值: {fmt_size(peak)}\n"
            f"📁 保存至: {OUTPUT_DIR.resolve()}\n"
            f"   (设置环境变量 CHINATXTBOOK_OUTPUT_DIR 可更改)"
        )

        # Scrollable book list (shows ALL books)
        book_list = self.query_one("#confirm-book-list", RichLog)
        for i, b in enumerate(selected_books, 1):
            name = b.get("name", b.get("key", "?"))
            sz = fmt_size(b.get("size", 0))
            parts = f"{b.get('part_count', 1)}卷"
            book_list.write(f"  {i:3}. {name[:45]}  {parts}  {sz}")

        disk = self.query_one("#confirm-disk", Static)
        yes_btn = self.query_one("#confirm-yes", Button)
        if usage.free < peak:
            disk.update(
                f"⛔ 磁盘空间不足\n需要峰值: {fmt_size(peak)} | "
                f"可用: {fmt_size(usage.free)}\n请清理空间后重试"
            )
            disk.add_class("notification-error")
            yes_btn.disabled = True
        else:
            disk.update(f"💿 磁盘可用: {free_gb:.1f} GB")

        yes_btn.focus()

    def action_focus_next_button(self):
        """Cycle focus between the two buttons."""
        focused = self.focused
        yes_btn = self.query_one("#confirm-yes", Button)
        no_btn = self.query_one("#confirm-no", Button)
        if focused == yes_btn:
            no_btn.focus()
        else:
            yes_btn.focus()

    def key_enter(self):
        """Enter confirms download."""
        yes_btn = self.query_one("#confirm-yes", Button)
        if not yes_btn.disabled:
            self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_dismiss(self) -> None:
        self.dismiss(False)
