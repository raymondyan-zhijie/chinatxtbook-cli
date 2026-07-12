"""Catalog Tree Widget — left panel.

4-level TreeView: 学段 → 科目 → 年级/册次 → 教材.
Keyboard: Space to select, arrows to navigate, Enter for detail.
"""

from textual.widgets import Tree

from chinatxtbook.core.git_client import GitClient
from chinatxtbook.core.manifest import SPLIT_RE
from chinatxtbook.utils.format import fmt_size


class CatalogTreeWidget(Tree):
    """SCR-BROWSE left panel: hierarchical textbook catalog."""

    def __init__(self, *args, **kwargs):
        super().__init__("📚 教材目录", *args, **kwargs)
        self._git_client: GitClient | None = None
        self._size_cache: dict = {}
        self._selected_node_ids: set = set()

    def set_git_client(self, client: GitClient, size_cache: dict = None):
        self._git_client = client
        if size_cache:
            self._size_cache = size_cache

    def load_catalog(self, top_dirs: list[str] = None):
        """Populate tree from git repository data."""
        self.root.remove_children()
        self._selected_node_ids.clear()

        if not self._git_client or not self._git_client.is_repo_valid():
            self.root.add("📦 仓库未初始化 — 按 F5", expand=False)
            return

        tops = top_dirs or ["小学", "初中", "高中"]
        import os
        from pathlib import Path

        for top in tops:
            if not self._git_client.path_exists_in_tree(top):
                continue

            all_files = self._git_client.ls_tree(top, recursive=True)
            if not all_files:
                continue

            # Group split files by directory
            groups_by_dir: dict = {}
            for f in all_files:
                name = os.path.basename(f)
                m = SPLIT_RE.match(name)
                if not m:
                    continue
                base = m.group(1)
                idx = int(m.group(2))
                rel_dir = str(Path(f).parent.as_posix())
                groups_by_dir.setdefault(rel_dir, {}).setdefault(base, {})[idx] = name

            if not groups_by_dir:
                continue

            stage_node = self.root.add(f"📁 {top}", expand=True)
            stage_node.data = {"type": "stage", "path": top}

            for dir_path in sorted(groups_by_dir):
                groups = groups_by_dir[dir_path]
                parts_path = dir_path.split("/")
                subject_name = parts_path[1] if len(parts_path) > 1 else dir_path

                subject_node = stage_node.add(
                    f"📂 {subject_name} ({len(groups)})", expand=True)
                subject_node.data = {"type": "subject", "path": dir_path}

                for base_name, parts in sorted(groups.items()):
                    key = f"{dir_path}/{base_name}"
                    total_size = sum(
                        self._size_cache.get(f"{dir_path}/{p}", 0)
                        for p in parts.values()
                    )
                    size_str = f" ({fmt_size(total_size)})" if total_size else ""
                    label = f"📄 {base_name} [{len(parts)}卷]{size_str}"

                    # Show selection state
                    app = self.app
                    if hasattr(app, 'selected_keys') and key in app.selected_keys:
                        label = f"☑ {base_name} [{len(parts)}卷]{size_str}"

                    book_node = subject_node.add(label, expand=False)
                    book_node.data = {
                        "type": "book", "path": dir_path, "base": base_name,
                        "key": key, "parts": parts,
                        "size": total_size, "part_count": len(parts),
                    }

        self.root.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Space: toggle selection for books. Enter: show detail overlay."""
        if not event.node or not event.node.data:
            return

        data = event.node.data
        if data.get("type") != "book":
            return

        key = data.get("key", "")
        app = self.app

        # Toggle selection state
        if hasattr(app, 'toggle_book_selection'):
            app.toggle_book_selection(key, data)
        event.stop()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Update app's focused_book on arrow navigation."""
        if event.node and event.node.data:
            data = event.node.data
            if data.get("type") == "book":
                app = self.app
                if hasattr(app, 'focused_book'):
                    app.focused_book = data
