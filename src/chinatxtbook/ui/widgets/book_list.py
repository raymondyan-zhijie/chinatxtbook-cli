"""Book List Widget — center panel.

Shows files in the currently highlighted directory.
Split files (.pdf.1, .pdf.2...) are grouped as one logical book.
Space toggles selection.
"""

import os
from pathlib import Path

from textual.widgets import DataTable

from chinatxtbook.core.manifest import SPLIT_RE
from chinatxtbook.utils.format import fmt_size


class BookListWidget(DataTable):
    """Center panel: files in the selected directory.

    Split parts are aggregated into one logical book per row.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_path: str = ""
        self._all_groups: dict = {}  # key -> {name, parts, size, ...}

    def on_mount(self) -> None:
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("", "教材名称", "分卷", "大小")

    def load_directory(self, git_client, dir_path: str, size_cache: dict = None):
        """Load all files in a directory, grouping split parts together."""
        self.clear()
        self._all_groups.clear()
        self._current_path = dir_path

        if not git_client or not git_client.is_repo_valid():
            self.add_row("", "仓库未初始化", "", "")
            return

        # Get ALL files recursively under this path
        all_files = git_client.ls_tree(dir_path, recursive=True)

        # Also get direct ls-tree entries to check for subdirectories
        ok, out, _ = git_client.run(
            ["ls-tree", "HEAD", "--", dir_path.rstrip("/")], retry=1
        )
        has_subdirs = False
        if ok:
            import re
            for line in out.strip().split("\n"):
                if line.strip():
                    parts = re.split(r'\s+', line.strip(), maxsplit=3)
                    if len(parts) >= 2 and parts[1] == "tree":
                        has_subdirs = True
                        break

        # Process files
        from chinatxtbook.core.manifest import SPLIT_RE as split_re

        # Group: {base_name: {idx: (filename, full_path)}}
        groups: dict = {}
        singles: dict = {}  # Non-split PDFs: {filename: full_path}

        for f in all_files:
            name = os.path.basename(f)
            m = split_re.match(name)
            if m:
                base = m.group(1)
                idx = int(m.group(2))
                groups.setdefault(base, {})[idx] = (name, f)
            elif name.lower().endswith(".pdf"):
                singles[name] = f

        # Add split groups as single rows
        for base_name, parts in sorted(groups.items()):
            key = f"{dir_path}/{base_name}"
            # Calculate total size
            total_size = 0
            if size_cache:
                for idx, (fname, fpath) in parts.items():
                    total_size += size_cache.get(fpath, 0)

            book_data = {
                "key": key, "name": base_name, "path": dir_path,
                "part_count": len(parts), "parts": parts,
                "size": total_size, "status": "not_downloaded",
            }
            self._all_groups[key] = book_data
            sz_str = fmt_size(total_size) if total_size else "?"
            self.add_row(
                "⬜", base_name, f"{len(parts)}卷", sz_str
            )

        # Add single PDFs
        for name, fpath in sorted(singles.items()):
            key = f"{dir_path}/{name}"
            total_size = 0
            if size_cache:
                total_size = size_cache.get(fpath, 0)

            book_data = {
                "key": key, "name": name, "path": dir_path,
                "part_count": 1, "parts": {1: (name, fpath)},
                "size": total_size, "status": "not_downloaded",
            }
            self._all_groups[key] = book_data
            sz_str = fmt_size(total_size) if total_size else "?"
            self.add_row("⬜", name, "1卷", sz_str)

        # If no files, show message
        if not groups and not singles:
            if has_subdirs:
                self.add_row("", "📂 此目录下还有子目录，请继续展开", "", "")
            else:
                self.add_row("", "此目录下无教材文件", "", "")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Space/Enter: toggle selection."""
        if event.row_key is None:
            return
        try:
            row_data = self.get_row(event.row_key)
            name = str(row_data[1])
            if name.startswith("📂") or not name:
                return

            # Find matching key
            key = f"{self._current_path}/{name}"
            # Try without path prefix (for grouped books)
            for bk_key, bk_data in self._all_groups.items():
                if bk_data["name"] == name:
                    key = bk_key
                    break

            # Toggle checkmark
            current = str(row_data[0])
            app = self.app
            if current == "⬜":
                self.update_cell(event.row_key, "", "☑")
                if hasattr(app, 'toggle_book_selection'):
                    app.toggle_book_selection(key, self._all_groups.get(key, {}))
            else:
                self.update_cell(event.row_key, "", "⬜")
                if hasattr(app, 'toggle_book_selection'):
                    app.toggle_book_selection(key, self._all_groups.get(key, {}))
        except Exception:
            pass

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Update detail panel on row focus."""
        if event.row_key is None:
            return
        try:
            row_data = self.get_row(event.row_key)
            name = str(row_data[1])
            if name.startswith("📂") or not name:
                return

            for bk_key, bk_data in self._all_groups.items():
                if bk_data["name"] == name:
                    app = self.app
                    if hasattr(app, 'focused_book'):
                        setattr(app, 'focused_book', bk_data)
                    break
        except Exception:
            pass
