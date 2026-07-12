"""Book List Widget — center panel.

Shows selected books with name, part count, size, and status.
Tracks selections from the catalog tree.
"""

from textual.widgets import DataTable

from chinatxtbook.ui.messages import (
    BookFocused, BookSelected, SelectionChanged, CatalogLoaded,
)
from chinatxtbook.utils.format import fmt_size


class BookListWidget(DataTable):
    """DataTable tracking currently selected books.

    Columns: Name, Parts, Size, Status.
    Updated as user selects/deselects books in the catalog tree.
    """

    STATUS_ICONS = {
        "not_downloaded": "⬜",
        "downloading":    "⬇️",
        "downloaded":     "✅",
        "merging":        "🔄",
        "merged":         "✔️",
        "verified":       "💚",
        "failed":         "❌",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._book_rows: dict = {}  # key -> row_key

    def on_mount(self) -> None:
        """Initialize table columns."""
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("", "教材名称", "分卷", "大小", "状态")

    def on_catalog_loaded(self, message: CatalogLoaded) -> None:
        """Clear selection list when catalog reloads."""
        self.clear()
        self._book_rows.clear()

    def add_book(self, book_data: dict) -> None:
        """Add a book to the selected list."""
        key = book_data.get("key", "")
        if key in self._book_rows:
            return  # Already in list
        name = book_data.get("name", book_data.get("base", "?"))
        parts = f"{book_data.get('part_count', '?')}卷"
        size_str = fmt_size(book_data.get("size", 0))
        status = book_data.get("status", "未下载")
        icon = self.STATUS_ICONS.get(status, "⬜")
        try:
            self._book_rows[key] = self.add_row(icon, name, parts, size_str, status)
        except Exception:
            pass

    def remove_book(self, key: str) -> None:
        """Remove a book from the selected list."""
        if key in self._book_rows:
            try:
                self.remove_row(self._book_rows[key])
            except Exception:
                pass
            del self._book_rows[key]

    def on_book_selected(self, message: BookSelected) -> None:
        """React to book selection changes from the catalog tree."""
        if message.selected:
            self.add_book({
                "key": message.key,
                "name": message.key.rsplit("/", 1)[-1] if "/" in message.key else message.key,
            })
        else:
            self.remove_book(message.key)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Forward focused book data to detail panel."""
        if event.row_key is not None:
            try:
                row = self.get_row(event.row_key)
                self.post_message(BookFocused(book_data={
                    "name": str(row[1]),
                    "parts": str(row[2]),
                    "size": str(row[3]),
                    "status": str(row[4]),
                }))
            except Exception:
                pass

    def update_book_status(self, key: str, status: str, detail: str = "") -> None:
        """Update a book's status icon in the table."""
        icon = self.STATUS_ICONS.get(status, "⬜")
        for row_key, row_data in self._book_rows.items():
            if row_key == key:
                try:
                    self.update_cell(row_data, "", icon)
                    self.update_cell(row_data, "状态", status)
                except Exception:
                    continue
                break
