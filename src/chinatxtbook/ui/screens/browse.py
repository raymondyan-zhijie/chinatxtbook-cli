"""SCR-BROWSE — Main browsing interface.

Left: GitHub repo directory tree. Center: files in selected directory.
Right: file details. Bottom: selection status + hints.
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
        self.set_timer(0.2, self._init_catalog)

    def _init_catalog(self) -> None:
        app = self.app
        bar = self.query_one("#status-bar", StatusBarWidget)

        if not hasattr(app, 'git_client') or not app.git_client:
            bar.update_status("Git client not ready")
            return
        if not app.git_client.is_repo_valid():
            bar.update_status("Repo not initialized - press F5 to clone")
            return

        bar.update_status("Loading catalog...")
        tree = self.query_one("#catalog-tree", CatalogTreeWidget)
        tree.set_git_client(app.git_client)
        tree.load_top_dirs(list(DEFAULT_TOP_DIRS))

        children = list(tree.root.children)
        if children:
            bar.update_status(f"Catalog loaded: {len(children)} stages")
        else:
            bar.update_status("Catalog empty - check repo state")

        bar.update_info(
            len(getattr(app, 'selected_keys', set())),
            getattr(app, 'estimated_size', 0),
        )
