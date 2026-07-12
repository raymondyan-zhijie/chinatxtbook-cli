"""Search Bar Widget — overlay search.

Activated by '/' key. Filters the catalog tree and book list in real-time.
"""

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Input, Static

from chinatxtbook.ui.messages import SearchQuery


class SearchBarWidget(Container):
    """Overlay search bar, shown when '/' is pressed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("搜索教材 — 输入关键词实时筛选，ESC 关闭", classes="search-hint")
            yield Input(placeholder="输入教材名称、科目或年级...", id="search-input")

    def on_mount(self) -> None:
        """Hide by default; shown on '/' key."""
        self.display = False
        self.add_class("hidden")

    def toggle(self) -> None:
        """Show/hide and focus the search input."""
        self.display = not self.display
        if self.display:
            self.remove_class("hidden")
            self.add_class("visible")
            inp = self.query_one("#search-input", Input)
            inp.focus()
        else:
            self.remove_class("visible")
            self.add_class("hidden")
            inp = self.query_one("#search-input", Input)
            inp.value = ""

    def on_input_changed(self, event: Input.Changed) -> None:
        """Post search query on each keystroke (debounced by Textual)."""
        if event.input.id == "search-input":
            self.post_message(SearchQuery(query=event.value))
