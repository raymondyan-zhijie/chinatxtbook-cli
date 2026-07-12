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
            self._check_software_update()
        elif event.button.id == "update-check-repo":
            self._check_textbook_update()

    def _check_software_update(self):
        """Check GitHub Releases API for newer versions."""
        import urllib.request, json
        soft = self.query_one("#update-software", Static)
        soft.update(f"当前版本: v{VERSION}\n正在检查 GitHub Releases...")
        try:
            url = "https://api.github.com/repos/raymondyan-zhijie/chinatxtbook-cli/releases/latest"
            req = urllib.request.Request(url, headers={
                "User-Agent": f"ChinaTextbook/{VERSION}",
                "Accept": "application/vnd.github+json",
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                latest = data.get("tag_name", "").lstrip("v")
                if latest and latest != VERSION:
                    soft.update(f"当前版本: v{VERSION}\n新版本: v{latest}\n{data.get('html_url','')}")
                else:
                    soft.update(f"当前版本: v{VERSION}\n已是最新版本 ✓")
        except Exception as e:
            soft.update(f"当前版本: v{VERSION}\n无法检查更新: {str(e)[:60]}")

    def _check_textbook_update(self):
        """Check textbook repo for updates via git fetch."""
        text = self.query_one("#update-textbook", Static)
        text.update("正在检查教材仓库更新...")
        app = self.app
        if app and hasattr(app, 'git_client') and app.git_client:
            try:
                git = app.git_client
                branch = app.state.get("default_branch", "master")
                old = git.get_head_commit()
                git.fetch(branch)
                new = git.rev_parse(f"origin/{branch}")
                if old and new and old != new:
                    text.update(f"发现教材更新\n{old[:8]} → {new[:8]}\n按 F5 下载更新后的教材")
                else:
                    text.update("教材仓库已是最新 ✓")
            except Exception as e:
                text.update(f"无法检查教材更新: {str(e)[:60]}")
        else:
            text.update("仓库未初始化，无法检查更新")

    def action_dismiss(self) -> None:
        self.dismiss()
