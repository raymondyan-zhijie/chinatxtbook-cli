"""Book List Widget — center panel.

Shows files in the currently highlighted directory.
Split files (.pdf.1, .pdf.2...) are grouped as one logical book.
Space/Enter toggles selection.
"""

from textual.widgets import DataTable
from textual.binding import Binding

from chinatxtbook.ui.messages import BookFocused
from chinatxtbook.utils.format import fmt_size


class BookListWidget(DataTable):
    """Center panel: files in selected directory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_path: str = ""
        self._all_groups: dict = {}

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("", "教材名称", "分卷", "大小")

    # ── Data loading ─────────────────────────────────────────

    def load_directory(self, git_client, dir_path: str, size_cache: dict = None):
        """Load files in a directory, grouping split parts."""
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

        # Add split groups
        for base_name, parts in sorted(groups.items()):
            key = f"{dir_path}/{base_name}"
            sz = sum(size_cache.get(fpath, 0) for _, fpath in parts.values()) if size_cache else 0
            self._all_groups[key] = {
                "key": key, "name": base_name, "path": dir_path,
                "part_count": len(parts), "parts": parts,
                "size": sz, "status": "not_downloaded",
            }
            self.add_row("⬜", base_name, f"{len(parts)}卷", fmt_size(sz) if sz else "?")

        # Add single PDFs
        for name, fpath in sorted(singles.items()):
            key = f"{dir_path}/{name}"
            sz = size_cache.get(fpath, 0) if size_cache else 0
            self._all_groups[key] = {
                "key": key, "name": name, "path": dir_path,
                "part_count": 1, "parts": {1: (name, fpath)},
                "size": sz, "status": "not_downloaded",
            }
            self.add_row("⬜", name, "1卷", fmt_size(sz) if sz else "?")

        if not groups and not singles:
            self.add_row("", "展开到底层目录查看教材文件", "", "")

    # ── Selection ────────────────────────────────────────────

    def key_space(self) -> None:
        """Space: toggle selection of current row."""
        row_key = self.cursor_row
        if row_key is None:
            return
        self._do_toggle(row_key)
        # Confirm toggle with a brief notification
        if hasattr(self, 'app') and hasattr(self.app, 'notify'):
            pass  # Notifications are too noisy for every Space press

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Enter/click: toggle selection."""
        self._do_toggle(event.row_key)

    def _do_toggle(self, row_key) -> None:
        """Toggle checkmark and notify app."""
        try:
            row = self.get_row(row_key)
            name = str(row[1])
            if not name or name.startswith("📂") or name.startswith("展开"):
                return

            current = str(row[0])
            app = self.app

            # Find book data
            bk_data = None
            for d in self._all_groups.values():
                if d["name"] == name:
                    bk_data = d
                    break
            if not bk_data:
                return

            if current == "☑":
                # Deselect
                self.update_cell(row_key, "", "⬜")
                if hasattr(app, 'selected_keys'):
                    app.selected_keys.discard(bk_data["key"])
            else:
                # Select
                self.update_cell(row_key, "", "☑")
                if hasattr(app, 'selected_keys'):
                    app.selected_keys.add(bk_data["key"])
                if hasattr(app, 'focused_book'):
                    app.focused_book = bk_data
                self.post_message(BookFocused(book_data=bk_data))

            # Update estimated size and status bar
            if hasattr(app, '_catalog_books'):
                app._catalog_books = list(self._all_groups.values())
            if hasattr(app, 'estimated_size'):
                app.estimated_size = sum(
                    d["size"] for d in self._all_groups.values()
                    if d["key"] in getattr(app, 'selected_keys', set())
                )
            if hasattr(app, '_update_status_bar'):
                app._update_status_bar()

        except Exception as e:
            import traceback
            traceback.print_exc()

    # ── Focus ────────────────────────────────────────────────

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update detail panel on row focus."""
        if event.row_key is None:
            return
        try:
            row = self.get_row(event.row_key)
            name = str(row[1])
            for d in self._all_groups.values():
                if d["name"] == name:
                    app = self.app
                    if hasattr(app, 'focused_book'):
                        app.focused_book = d
                    self.post_message(BookFocused(book_data=d))
                    break
        except Exception:
            pass
