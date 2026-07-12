"""Book List Widget -- center panel.

ListView with ListItem children per design doc 2.2.
Space/Enter natively toggles selection.
"""

from textual.widgets import ListView, ListItem, Label


class BookListWidget(ListView):
    """Center panel: books in the selected directory.

    Space/Enter: toggle selection (native ListView behavior).
    Arrow keys: move focus.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_path: str = ""
        # Metadata stored separately: key -> {name, parts, size, ...}
        self._book_meta: dict = {}       # list_index -> book_data
        self._all_groups: dict = {}      # key -> book_data

    def on_mount(self) -> None:
        self.border_title = "教材列表"

    def load_directory(self, git_client, dir_path: str, size_cache: dict = None):
        """Load books in a directory, grouping split parts."""
        self.clear()
        self._book_meta.clear()
        self._all_groups.clear()
        self._current_path = dir_path

        if not git_client or not git_client.is_repo_valid():
            return

        import os
        from chinatxtbook.core.manifest import SPLIT_RE
        from chinatxtbook.utils.format import fmt_size

        all_files = git_client.ls_tree(dir_path, recursive=True)
        groups: dict = {}
        singles: dict = {}

        for f in all_files:
            name = os.path.basename(f)
            m = SPLIT_RE.match(name)
            if m:
                base = m.group(1)
                idx = int(m.group(2))
                groups.setdefault(base, {})[idx] = (name, f)
            elif name.lower().endswith(".pdf"):
                singles[name] = f

        app = self.app
        selected_keys = getattr(app, 'selected_keys', set()) if app else set()
        idx = 0

        # Add split groups
        for base_name, parts in sorted(groups.items()):
            key = f"{dir_path}/{base_name}"
            sz = sum(size_cache.get(fpath, 0) for _, fpath in parts.values()) if size_cache else 0
            self._all_groups[key] = {
                "key": key, "name": base_name, "path": dir_path,
                "part_count": len(parts), "parts": parts,
                "size": sz, "status": "not_downloaded",
            }
            check = "☑" if key in selected_keys else "⬜"
            sz_str = fmt_size(sz) if sz else "?"
            label = f"{check}  {base_name}  │  {len(parts)}卷  │  {sz_str}"
            item = ListItem(Label(label))
            self.append(item)
            self._book_meta[idx] = self._all_groups[key]
            idx += 1

        # Add single PDFs
        for name, fpath in sorted(singles.items()):
            key = f"{dir_path}/{name}"
            sz = size_cache.get(fpath, 0) if size_cache else 0
            self._all_groups[key] = {
                "key": key, "name": name, "path": dir_path,
                "part_count": 1, "parts": {1: (name, fpath)},
                "size": sz, "status": "not_downloaded",
            }
            check = "☑" if key in selected_keys else "⬜"
            sz_str = fmt_size(sz) if sz else "?"
            label = f"{check}  {name}  │  1卷  │  {sz_str}"
            item = ListItem(Label(label))
            self.append(item)
            self._book_meta[idx] = self._all_groups[key]
            idx += 1

        if not groups and not singles:
            item = ListItem(Label("展开到底层目录查看教材文件"))
            self.append(item)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Space/Enter: toggle selection via native ListView."""
        if event.item is None:
            return
        # Find the index of the selected item
        try:
            idx = self.children.index(event.item)
        except ValueError:
            return

        meta = self._book_meta.get(idx)
        if not meta:
            return
        key = meta["key"]
        app = self.app
        if not app or not hasattr(app, 'selected_keys'):
            return

        # Toggle in app state
        if key in app.selected_keys:
            app.selected_keys.discard(key)
        else:
            app.selected_keys.add(key)
            if hasattr(app, 'focused_book'):
                app.focused_book = meta

        # Recalculate size
        if hasattr(app, 'estimated_size'):
            app.estimated_size = sum(
                d["size"] for d in self._all_groups.values()
                if d["key"] in app.selected_keys
            )

        # Sync _catalog_books
        if hasattr(app, '_catalog_books'):
            app._catalog_books = list(self._all_groups.values())

        # Update status bar
        if hasattr(app, '_update_status_bar'):
            app._update_status_bar()

        # Refresh the item label with new checkmark
        selected = key in app.selected_keys
        check = "☑" if selected else "⬜"
        name = meta["name"]
        parts = f"{meta['part_count']}卷"
        from chinatxtbook.utils.format import fmt_size
        sz_str = fmt_size(meta["size"]) if meta["size"] else "?"
        new_label = f"{check}  {name}  │  {parts}  │  {sz_str}"

        # Update the ListItem's Label child
        try:
            label_widget = event.item.query_one(Label)
            label_widget.update(new_label)
        except Exception:
            pass

        event.stop()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update detail panel when highlight changes."""
        if event.item is None:
            return
        try:
            idx = self.children.index(event.item)
        except ValueError:
            return
        meta = self._book_meta.get(idx)
        if meta:
            app = self.app
            if app and hasattr(app, 'focused_book'):
                app.focused_book = meta
