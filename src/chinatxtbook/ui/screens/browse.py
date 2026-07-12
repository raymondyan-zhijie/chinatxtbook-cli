"""SCR-BROWSE — Main browsing interface.

Left: GitHub repo directory tree. Center: files in selected directory.
Right: file details. Bottom: selection status.
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
    """SCR-BROWSE: directory tree | file list | details."""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-panel"):
            yield CatalogTreeWidget(id="catalog-tree")
            yield BookListWidget(id="book-list")
            yield DetailPanelWidget(id="detail-panel")
        yield StatusBarWidget(id="status-bar")

    def on_mount(self) -> None:
        """Load top-level directories after screen is mounted."""
        self.set_timer(0.2, self._init_catalog)

    def _init_catalog(self) -> None:
        """Initialize the catalog tree from the Git workspace."""
        app = self.app
        if not hasattr(app, 'git_client') or not app.git_client:
            return
        if not app.git_client.is_repo_valid():
            return

        tree = self.query_one("#catalog-tree", CatalogTreeWidget)
        tree.set_git_client(app.git_client)

        tops = DEFAULT_TOP_DIRS
        if hasattr(app, 'state') and app.state:
            tops = app.state.get("selected_paths", DEFAULT_TOP_DIRS) or tops

        tree.load_top_dirs(list(tops))
