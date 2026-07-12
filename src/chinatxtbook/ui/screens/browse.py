"""SCR-BROWSE — Main browsing interface.

Three-panel layout: Catalog Tree | Book List | Detail Panel.
Default screen on app launch. Keyboard-driven with Space selection.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Header, Footer

from chinatxtbook.ui.widgets.catalog_tree import CatalogTreeWidget
from chinatxtbook.ui.widgets.book_list import BookListWidget
from chinatxtbook.ui.widgets.detail_panel import DetailPanelWidget
from chinatxtbook.ui.widgets.status_bar import StatusBarWidget


class BrowseScreen(Screen):
    """SCR-BROWSE: Main textbook browsing and selection screen.

    4-level TreeView (学段→科目→年级→教材) | DataTable book list | Detail panel.
    Default screen on launch. All other screens are pushed on top of this one.
    """

    BINDINGS = [
        # Handled at App level; screen-level bindings for local scope
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-panel"):
            yield CatalogTreeWidget(id="catalog-tree")
            yield BookListWidget(id="book-list")
            yield DetailPanelWidget(id="detail-panel")
        yield StatusBarWidget(id="status-bar")

    def on_mount(self) -> None:
        """Trigger catalog loading via the parent app."""
        app = self.app
        if hasattr(app, '_load_catalog'):
            app._load_catalog()
