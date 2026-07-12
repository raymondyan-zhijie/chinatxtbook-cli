"""SCR-BROWSE — Main browsing interface.

Three-panel layout: Catalog Tree | Book List | Detail Panel.
Self-contained catalog loading via set_timer for correct mount timing.
"""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Header

from chinatxtbook.config import DEFAULT_TOP_DIRS
from chinatxtbook.ui.widgets.catalog_tree import CatalogTreeWidget
from chinatxtbook.ui.widgets.book_list import BookListWidget
from chinatxtbook.ui.widgets.detail_panel import DetailPanelWidget
from chinatxtbook.ui.widgets.status_bar import StatusBarWidget


class BrowseScreen(Screen):
    """SCR-BROWSE: Main textbook browsing and selection screen."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-panel"):
            yield CatalogTreeWidget(id="catalog-tree")
            yield BookListWidget(id="book-list")
            yield DetailPanelWidget(id="detail-panel")
        yield StatusBarWidget(id="status-bar")

    def on_mount(self) -> None:
        """Load catalog after screen is fully mounted."""
        # Defer loading to ensure widgets are in the DOM
        self.set_timer(0.1, self._load_catalog)

    def _load_catalog(self) -> None:
        """Load the catalog tree from the Git workspace."""
        app = self.app
        if not hasattr(app, 'git_client') or not app.git_client:
            return
        if not app.git_client.is_repo_valid():
            return

        tree = self.query_one("#catalog-tree", CatalogTreeWidget)
        tree.set_git_client(app.git_client)

        # Use cached books from app, or load fresh
        tops = DEFAULT_TOP_DIRS
        if hasattr(app, 'state') and app.state:
            tops = app.state.get("selected_paths") or tops

        tree.load_catalog(tops)

        # Populate app's _catalog_books from tree data
        if hasattr(app, '_catalog_books'):
            books = []
            for node in tree.root.children:  # stage nodes
                for subj_node in node.children:  # subject nodes
                    for book_node in subj_node.children:  # book nodes
                        if book_node.data and book_node.data.get("type") == "book":
                            books.append(book_node.data)
            app._catalog_books = books

        # Update status bar
        bar = self.query_one("#status-bar", StatusBarWidget)
        count = len(getattr(app, 'selected_keys', set()))
        bar.update_info(count, getattr(app, 'estimated_size', 0))
