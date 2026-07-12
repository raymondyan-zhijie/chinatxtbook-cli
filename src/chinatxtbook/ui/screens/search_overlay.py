"""OVL-SEARCH — Global search overlay (/).

Real-time AND multi-keyword filtering across the catalog.
"""
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static, DataTable


class SearchOverlay(ModalScreen):
    """OVL-SEARCH: Search bar activated by '/' key.

    Filters catalog tree and book list in real-time.
    Enter to locate result, Esc to dismiss.
    """

    BINDINGS = [
        ("escape", "dismiss", "关闭"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="search-overlay"):
            yield Static("🔍 搜索教材 — 输入关键词实时筛选（AND 匹配），Enter 定位，Esc 关闭",
                         classes="search-hint")
            yield Input(placeholder="输入教材名称、科目或年级关键词...", id="search-input")
            yield Static("", id="search-results")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Real-time filter on each keystroke."""
        query = event.value.strip()
        results = self.query_one("#search-results", Static)
        if not query:
            results.update("")
            return

        # Search through catalog tree nodes
        app = self.app
        matches = []
        if hasattr(app, '_catalog_books'):
            keywords = query.lower().split()
            for book in app._catalog_books:
                text = f"{book.get('stage','')} {book.get('subject','')} "
                text += f"{book.get('grade','')} {book.get('name','')} "
                text += f"{book.get('key','')}".lower()
                if all(kw in text for kw in keywords):
                    matches.append(book)
                    if len(matches) >= 20:
                        break

        if matches:
            lines = [f"找到 {len(matches)} 个匹配:"] + [
                f"  📄 {b['name']} — {b.get('stage','')}/{b.get('subject','')}"
                for b in matches[:15]
            ]
            results.update("\n".join(lines))
        else:
            results.update("未找到匹配的教材")

    def action_dismiss(self) -> None:
        self.dismiss()
