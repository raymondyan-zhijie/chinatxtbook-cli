"""OVL-SEARCH — Global search overlay (/).

Real-time AND keyword filtering with interactive ListView.
Space selects, Enter locates, Esc dismisses.
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static, ListView, ListItem, Label
from textual.binding import Binding

from chinatxtbook.utils.format import fmt_size


class SearchOverlay(ModalScreen):
    """OVL-SEARCH: Interactive search with ListView results.

    Space: toggle selection. Enter: locate book in browse screen.
    Esc: dismiss.
    """

    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
        Binding("enter", "locate", "定位"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="search-overlay"):
            yield Static(
                "🔍 搜索 — 输入关键词，Space选择，Enter定位，Esc关闭", classes="search-hint"
            )
            yield Input(placeholder="输入教材名称、科目或年级...", id="search-input")
            yield ListView(id="search-results-list")
            yield Static("", id="search-status")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()
        self._matches: list = []

    def on_input_changed(self, event: Input.Changed) -> None:
        """Real-time AND filter on each keystroke."""
        query = event.value.strip()
        results = self.query_one("#search-results-list", ListView)
        status = self.query_one("#search-status", Static)
        results.clear()

        if not query:
            self._matches = []
            status.update("")
            return

        app = self.app
        keywords = query.lower().split()
        self._matches = []
        for book in getattr(app, "_catalog_books", []):
            text = (
                f"{book.get('stage','')} {book.get('subject','')} "
                f"{book.get('name','')} {book.get('key','')}"
            ).lower()
            if all(kw in text for kw in keywords):
                self._matches.append(book)
                if len(self._matches) >= 50:
                    break

        if self._matches:
            for book in self._matches:
                name = book.get("name", book.get("base", "?"))
                path = f"{book.get('stage','')}/{book.get('subject','')}"
                sz = fmt_size(book.get("size", 0)) if book.get("size") else "?"
                key = book.get("key", "")
                check = "☑" if key in getattr(app, "selected_keys", set()) else "⬜"
                label = f"{check} {name}  [{path}]  {sz}"
                results.append(ListItem(Label(label)))
            status.update(f"找到 {len(self._matches)} 个匹配 — Space选择 Enter定位")
        else:
            status.update("未找到匹配 — 减少关键词或检查路径")

    def action_locate(self) -> None:
        """Enter: locate to first/highlighted result and dismiss."""
        results = self.query_one("#search-results-list", ListView)
        if results.index is not None and self._matches:
            idx = results.index
            if idx < len(self._matches):
                book = self._matches[idx]
                app = self.app
                if hasattr(app, "focused_book"):
                    app.focused_book = book
                # Load the book's directory into the center panel
                path = book.get("path", "")
                if path and hasattr(app, "show_directory_files"):
                    app.show_directory_files(path)
                app.notify(f"已定位: {book.get('name','')[:40]}")
        self.dismiss()

    def action_dismiss(self) -> None:
        self.dismiss()
