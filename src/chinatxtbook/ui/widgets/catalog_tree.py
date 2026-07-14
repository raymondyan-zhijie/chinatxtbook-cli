"""Catalog Tree Widget — left panel.

Pure directory tree mirroring the GitHub repository structure exactly.
Lazy-loaded: children fetched from git on node expand.
"""

from textual.binding import Binding
from textual.widgets import Tree

from chinatxtbook.core.git_client import GitClient


class CatalogTreeWidget(Tree):
    """Left panel: exact mirror of GitHub repo directory tree.

    Shows directories only (no files). Lazy-loads children on expand.
    Highlighting a directory updates the center book list.
    """

    BINDINGS = [
        Binding("right", "expand_or_enter", "展开", show=False),
        Binding("left", "collapse_or_parent", "折叠", show=False),
    ]

    def action_expand_or_enter(self) -> None:
        """Right arrow: expand node, or step into first child if already expanded."""
        node = self.cursor_node
        if node is None:
            return
        if not node.is_expanded:
            node.expand()
        elif node.children:
            self.action_cursor_down()

    def action_collapse_or_parent(self) -> None:
        """Left arrow: collapse node, or move to parent if already collapsed."""
        node = self.cursor_node
        if node is None:
            return
        if node.is_expanded:
            node.collapse()
        else:
            self.action_cursor_parent()

    def __init__(self, *args, **kwargs):
        super().__init__("📁 仓库目录", *args, **kwargs)
        self._git_client: GitClient | None = None

    def set_git_client(self, client: GitClient):
        self._git_client = client

    def load_top_dirs(self, top_dirs: list[str]):
        """Load top-level directory nodes (学段 level)."""
        self.root.remove_children()
        if not self._git_client or not self._git_client.is_repo_valid():
            self.root.add("📦 仓库未初始化", expand=False)
            return

        for top in top_dirs:
            if not self._git_client.path_exists_in_tree(top):
                continue
            # Get subdirectories of this top dir
            children = self._git_client.ls_tree(f"{top}/") or []
            if not children:
                continue
            # Add root node with placeholder child (for expand arrow)
            node = self.root.add(f"📁 {top}", expand=False)
            node.data = {"type": "dir", "path": top, "loaded": False}
            # Add a dummy child so the expand arrow appears
            node.add(" ... ", expand=False)

        self.root.expand()
        self.focus()

    def _load_children(self, node) -> None:
        """Lazy-load children of a directory node from git tree."""
        if not self._git_client:
            return
        path = node.data.get("path", "")
        if not path:
            return

        # Get git tree entries for this path
        entries = self._git_client.ls_tree(f"{path}/") or []
        if not entries:
            return

        # Separate directories from files

        # Get unique parent directories for entries
        subdirs = set()
        for entry in entries:
            # entry might be like "小学/语文/统编版" (a dir)
            # or "小学/语文/统编版/file.pdf" (a file)
            if "/" in entry[len(path) + 1 :] if entry.startswith(path + "/") else False:
                # Has more path components - find the next directory level
                rel = entry[len(path) + 1 :] if entry.startswith(path + "/") else entry
                parts = rel.split("/")
                if len(parts) >= 1:
                    subdirs.add(parts[0])  # Next level directory name
            else:
                # Direct child
                pass

        # Use git ls-tree to get direct children
        # KEEP trailing slash so git lists directory contents
        ok, out, _ = self._git_client.run(["ls-tree", "HEAD", "--", f"{path}/"], retry=1)
        if not ok:
            return

        import re

        for line in out.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # git ls-tree output: <mode> <type> <hash>\t<full_path>
            # full_path includes the parent, e.g. "小学/语文"
            parts = re.split(r"\s+", line, maxsplit=3)
            if len(parts) < 4:
                continue
            _mode, obj_type, _obj_hash, full_name = parts[0], parts[1], parts[2], parts[3]
            # Extract just the basename for display
            name = full_name.split("/")[-1] if "/" in full_name else full_name

            if obj_type == "tree":
                # full_name is already the correct git path
                child_node = node.add(f"📁 {name}", expand=False)
                child_node.data = {"type": "dir", "path": full_name, "loaded": False}
                child_node.add(" ... ", expand=False)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Lazy-load children when a directory node is expanded."""
        node = event.node
        if not node or not node.data:
            return
        if node.data.get("type") != "dir":
            return
        if node.data.get("loaded"):
            return

        # Remove dummy placeholder
        node.remove_children()
        self._load_children(node)
        node.data["loaded"] = True

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Enter: load files for this directory into center panel.
        (Design: arrow keys = navigate, Enter = deliberate action to load files)"""
        node = event.node
        if not node or not node.data:
            return
        if node.data.get("type") != "dir":
            return
        path = node.data.get("path", "")
        if not path:
            return
        app = self.app
        if hasattr(app, "show_directory_files"):
            app.show_directory_files(path)
        event.stop()
