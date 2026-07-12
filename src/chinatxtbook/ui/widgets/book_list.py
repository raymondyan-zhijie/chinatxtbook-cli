"""Book List Widget -- center panel (ListView per design doc 2.2).

Shows books in the highlighted directory. Split files grouped as one book.
ListView natively supports Space/Enter selection.
"""

from textual.widgets import ListView, ListItem, Static
from textual.containers import Horizontal

from chinatxtbook.utils.format import fmt_size


class BookItem(ListItem):
    """A single book row in the list."""

    def __init__(self, book_key: str, name: str, parts: str, size: str,
                 selected: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.book_key = book_key
        self._name = name
        self._parts = parts
        self._size = size
        self._selected = selected

    def compose(self):
        check = "☑" if self._selected else "⬜"
        yield Static(f"{check}  {self._name}  │  {self._parts}  │  {self._size}")


class BookListWidget(ListView):
    """Center panel: books in the selected directory (ListView per 2.2).

    Space/Enter: toggle selection (native ListView behavior).
    Arrow keys: move focus.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_path: str = ""
        self._all_groups: dict = {}  # key -> book_data dict

    def on_mount(self) -> None:
        self.border_title = "教材列表"

    def load_directory(self, git_client, dir_path: str, size_cache: dict = None):
        """Load books in a directory, grouping split parts."""
        self.clear()
        self._all_groups.clear()
        self._current_path = dir_path

        if not git_client or not git_client.is_repo_valid():
            return

        import os
        from chinatxtbook.core.manifest import SPLIT_RE

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

        # Add split groups
        for base_name, parts in sorted(groups.items()):
            key = f"{dir_path}/{base_name}"
            sz = sum(size_cache.get(fpath, 0) for _, fpath in parts.values()) if size_cache else 0
            self._all_groups[key] = {
                "key": key, "name": base_name, "path": dir_path,
                "part_count": len(parts), "parts": parts,
                "size": sz, "status": "not_downloaded",
            }
            sel = key in selected_keys
            sz_str = fmt_size(sz) if sz else "?"
            item = BookItem(key, base_name, f"{len(parts)}卷", sz_str, selected=sel)
            self.append(item)

        # Add single PDFs
        for name, fpath in sorted(singles.items()):
            key = f"{dir_path}/{name}"
            sz = size_cache.get(fpath, 0) if size_cache else 0
            self._all_groups[key] = {
                "key": key, "name": name, "path": dir_path,
                "part_count": 1, "parts": {1: (name, fpath)},
                "size": sz, "status": "not_downloaded",
            }
            sel = key in selected_keys
            sz_str = fmt_size(sz) if sz else "?"
            item = BookItem(key, name, "1卷", sz_str, selected=sel)
            self.append(item)

        if not groups and not singles:
            item = BookItem("", "展开到底层目录查看教材文件", "", "", selected=False)
            self.append(item)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Space/Enter: toggle selection via native ListView event."""
        if not event.item or not isinstance(event.item, BookItem):
            return
        item = event.item
        key = item.book_key
        if not key:
            return

        app = self.app
        if not app or not hasattr(app, 'selected_keys'):
            return

        # Toggle in app state
        if key in app.selected_keys:
            app.selected_keys.discard(key)
        else:
            app.selected_keys.add(key)
            bk = self._all_groups.get(key, {})
            if bk and hasattr(app, 'focused_book'):
                app.focused_book = bk

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

        # Refresh this item's display
        self._refresh_item(item, key)

        # Stop event propagation
        event.stop()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Update detail panel and focused_book when highlight changes."""
        if not event.item or not isinstance(event.item, BookItem):
            return
        key = event.item.book_key
        if not key:
            return
        bk = self._all_groups.get(key, {})
        if bk:
            app = self.app
            if app and hasattr(app, 'focused_book'):
                app.focused_book = bk

    def _refresh_item(self, item: BookItem, key: str) -> None:
        """Update a BookItem's checkmark display."""
        app = self.app
        selected = key in app.selected_keys if app and hasattr(app, 'selected_keys') else False
        item._selected = selected
        try:
            item.remove_children()
            item.compose()
            item.mount()
        except Exception:
            pass
