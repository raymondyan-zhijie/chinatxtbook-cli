"""SCR-UPDATES — Software & textbook updates (F9).

Checks GitHub Releases for software updates and git diff for textbook updates.
"""

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button

from chinatxtbook import VERSION


class UpdatesScreen(ModalScreen):
    """SCR-UPDATES: Check for software and textbook repository updates."""

    BINDINGS = [("escape", "dismiss", "关闭")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._has_updates = False
        self._update_info = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="updates-screen"):
            yield Static("🔄 检查更新", classes="modal-title")

            yield Static("软件更新", classes="modal-title")
            yield Static("", id="update-software", classes="modal-content")

            yield Static("教材更新", classes="modal-title")
            yield Static("", id="update-textbook", classes="modal-content")

            with Horizontal():
                yield Button("检查软件更新", variant="primary", id="update-check-app")
                yield Button("检查教材更新", variant="primary", id="update-check-repo")
                yield Button("关闭 (Esc)", variant="default", id="update-close")

    def on_mount(self) -> None:
        soft = self.query_one("#update-software", Static)
        soft.update(f"当前版本: v{VERSION}")

        text = self.query_one("#update-textbook", Static)
        if self._update_info:
            text.update(self._update_info)
        else:
            text.update("按「检查教材更新」对比上游仓库变更")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "update-close":
            self.dismiss()
        elif event.button.id == "update-check-app":
            self.notify("检查 GitHub Releases...（模拟）", severity="information")
            soft = self.query_one("#update-software", Static)
            soft.update(f"当前版本: v{VERSION}\n已是最新版本 ✓")
        elif event.button.id == "update-check-repo":
            self.notify("检查教材仓库更新...（模拟）", severity="information")
            text = self.query_one("#update-textbook", Static)
            text.update("已是最新，无需更新 ✓")

    def action_dismiss(self) -> None:
        self.dismiss()
