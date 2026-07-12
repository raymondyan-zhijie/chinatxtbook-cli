"""Domain models for ChinaTextbook v1.1.

Per design doc 2.3: immutable dataclasses for Book, SourceFile, Task, etc.
BookId = "bk_" + SHA256(logical_path)[:24] per Section 5.3.
"""
from chinatxtbook.models.book import Book, SourceFile, SourceKind, make_book_id
from chinatxtbook.models.task import TaskRecord, TaskState, TaskStage, TaskKind, TaskProgress
from chinatxtbook.models.events import AppEvent
from chinatxtbook.models.errors import ErrorCode, DomainError
