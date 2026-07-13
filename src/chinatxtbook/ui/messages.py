"""Textual message types for UI state updates.

Messages are posted by workers and handled by widgets to update the UI.
"""

from textual.message import Message


class CatalogLoaded(Message):
    """Posted when the catalog tree has been built."""

    def __init__(self, root_node=None):
        super().__init__()
        self.root_node = root_node


class BookSelected(Message):
    """Posted when a book selection changes."""

    def __init__(self, key: str, selected: bool):
        super().__init__()
        self.key = key
        self.selected = selected


class BookFocused(Message):
    """Posted when a book receives focus (for detail panel)."""

    def __init__(self, book_data: dict = None):
        super().__init__()
        self.book_data = book_data or {}


class SelectionChanged(Message):
    """Posted when the selection set changes."""

    def __init__(self, selected_count: int, estimated_size: int = 0):
        super().__init__()
        self.selected_count = selected_count
        self.estimated_size = estimated_size


class BookStatusChanged(Message):
    """Posted when a book's download/merge status changes."""

    def __init__(self, key: str, status: str, detail: str = ""):
        super().__init__()
        self.key = key
        self.status = status
        self.detail = detail


class DownloadProgress(Message):
    """Posted periodically during download/merge."""

    def __init__(
        self,
        overall_pct: float,
        current_file: str = "",
        speed_bytes: float = 0,
        eta_seconds: float = 0,
        done_count: int = 0,
        total_count: int = 0,
    ):
        super().__init__()
        self.overall_pct = overall_pct
        self.current_file = current_file
        self.speed_bytes = speed_bytes
        self.eta_seconds = eta_seconds
        self.done_count = done_count
        self.total_count = total_count


class PipelineStarted(Message):
    """Posted when the download pipeline starts."""

    def __init__(self, total_books: int):
        super().__init__()
        self.total_books = total_books


class PipelineCompleted(Message):
    """Posted when the download pipeline finishes."""

    def __init__(self, success_count: int, fail_count: int, skip_count: int):
        super().__init__()
        self.success_count = success_count
        self.fail_count = fail_count
        self.skip_count = skip_count


class RepoStatusChanged(Message):
    """Posted when repository state changes."""

    def __init__(self, status: str, detail: str = ""):
        super().__init__()
        self.status = status
        self.detail = detail


class LogMessage(Message):
    """Posted for each log entry (consumed by LogWindow)."""

    def __init__(self, level: str, message: str):
        super().__init__()
        self.level = level
        self.message = message


class SearchQuery(Message):
    """Posted when the user types in the search bar."""

    def __init__(self, query: str):
        super().__init__()
        self.query = query
