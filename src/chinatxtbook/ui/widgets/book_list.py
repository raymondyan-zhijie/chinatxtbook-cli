"""Book List Widget -- center panel.

ListView with ListItem children per design doc 2.2.
Space/Enter natively toggles selection.
"""

import os
from pathlib import Path

from textual.widgets import ListView, ListItem, Label
from textual.binding import Binding

from chinatxtbook.ui.messages import BookFocused
from chinatxtbook.utils.format import fmt_size


class BookListWidget(ListView):
    """Center panel: books in the selected directory.

    Space/Enter: toggle selection. Arrow keys: move focus.
    """

    BINDINGS = [
        Binding("space", "select", "选择", show=False),
    ]

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
            # Use actual file directory (from first part's full path), not navigation dir
            first_path = list(parts.values())[0][1]  # full git path of first part
            actual_dir = str(Path(first_path).parent.as_posix())
            key = f"{actual_dir}/{base_name}"
            sz = sum(size_cache.get(fpath, 0) for _, fpath in parts.values()) if size_cache else 0
            self._all_groups[key] = {
                "key": key, "name": base_name, "path": actual_dir,
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
            # Use actual file directory from full git path
            actual_dir = str(Path(fpath).parent.as_posix())
            key = f"{actual_dir}/{name}"
            sz = size_cache.get(fpath, 0) if size_cache else 0
            self._all_groups[key] = {
                "key": key, "name": name, "path": actual_dir,
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

    def action_select(self) -> None:
        """Space: manually trigger selection (in case native ListView
        Space handling is overridden by parent bindings)."""
        if self.index is not None:
            item = self.children[self.index] if self.index < len(self.children) else None
            if item:
                self._toggle_item(item, self.index)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter/click: toggle selection via native ListView."""
        if event.item is None:
            return
        try:
            idx = self.children.index(event.item)
        except ValueError:
            return
        self._toggle_item(event.item, idx)
        event.stop()

    def _toggle_item(self, item, idx: int) -> None:
        """Toggle selection for an item at given index."""
        meta = self._book_meta.get(idx)
        if not meta:
            return
        key = meta["key"]
        app = self.app
        if not app or not hasattr(app, 'selected_keys'):
            return

        # Toggle
        if key in app.selected_keys:
            app.selected_keys.discard(key)
        else:
            app.selected_keys.add(key)
            if hasattr(app, 'focused_book'):
                app.focused_book = meta

        # Recalculate
        if hasattr(app, 'estimated_size'):
            app.estimated_size = sum(
                d["size"] for d in self._all_groups.values()
                if d["key"] in app.selected_keys
            )
        if hasattr(app, '_catalog_books'):
            app._catalog_books = list(self._all_groups.values())
        if hasattr(app, '_update_status_bar'):
            app._update_status_bar()

        # Refresh label
        selected = key in app.selected_keys
        check = "☑" if selected else "⬜"
        name = meta["name"]
        from chinatxtbook.utils.format import fmt_size
        sz_str = fmt_size(meta["size"]) if meta["size"] else "?"
        new_label = f"{check}  {name}  │  {meta['part_count']}卷  │  {sz_str}"

        try:
            label_widget = item.query_one(Label)
            label_widget.update(new_label)
        except Exception:
            pass

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
