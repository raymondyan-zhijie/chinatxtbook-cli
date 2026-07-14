"""SCR-BROWSE - Main browsing interface.

Left: GitHub repo directory tree. Center: files in selected directory.
Right: file details. Bottom: selection status + hints.
"""

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Header

from chinatxtbook.config import DEFAULT_TOP_DIRS
from chinatxtbook.ui.widgets.catalog_tree import CatalogTreeWidget
from chinatxtbook.ui.widgets.book_list import BookListWidget
from chinatxtbook.ui.widgets.detail_panel import DetailPanelWidget
from chinatxtbook.ui.widgets.status_bar import StatusBarWidget

if TYPE_CHECKING:
    from chinatxtbook.ui.app import ChinaTextbookApp


class BrowseScreen(Screen):
    """SCR-BROWSE: directory tree | file list | details."""

    BINDINGS = [
        Binding("ctrl+a", "select_all", "全选"),
    ]

    def action_select_all(self):
        app = self.app
        if hasattr(app, "action_select_all"):
            app.action_select_all()

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
        app = cast("ChinaTextbookApp", self.app)
        bar = self.query_one("#status-bar", StatusBarWidget)

        if not hasattr(app, "git_client") or not app.git_client:
            bar.update_status("Git client not ready")
            return
        if not app.git_client.is_repo_valid():
            bar.update_status("Repo not initialized - press F5 to clone")
            return

        bar.update_status("Loading catalog...")

        # Populate size cache from GitHub API (async in background)
        git = app.git_client
        if not app.state.get("size_cache"):
            bar.update_status("Fetching file sizes from GitHub API...")
            try:
                commit = git.get_head_commit()
                dirs, files, truncated = git.get_remote_sizes(
                    commit or app.state.get("default_branch", "master")
                )
                if dirs:
                    app.state["size_cache"] = {
                        "commit": commit,
                        "dirs": dirs,
                        "files": files,
                        "truncated": truncated,
                    }
                    app.state_mgr.save(app.state)
            except Exception:
                pass  # Size cache is optional

        tree = self.query_one("#catalog-tree", CatalogTreeWidget)
        tree.set_git_client(app.git_client)
        tree.load_top_dirs(list(DEFAULT_TOP_DIRS))

        children = list(tree.root.children)
        if children:
            bar.update_status(f"Catalog loaded: {len(children)} stages")
        else:
            bar.update_status("Catalog empty - check repo state")

        bar.update_info(
            len(getattr(app, "selected_keys", set())),
            getattr(app, "estimated_size", 0),
        )
