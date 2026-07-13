"""Domain models for ChinaTextbook v1.1.

Per design doc 2.3: immutable dataclasses for Book, SourceFile, Task, etc.
BookId = "bk_" + SHA256(logical_path)[:24] per Section 5.3.
"""
from chinatxtbook.models.book import Book as Book
from chinatxtbook.models.book import SourceFile as SourceFile
from chinatxtbook.models.book import SourceKind as SourceKind
from chinatxtbook.models.book import make_book_id as make_book_id
from chinatxtbook.models.task import TaskRecord as TaskRecord
from chinatxtbook.models.task import TaskState as TaskState
from chinatxtbook.models.task import TaskStage as TaskStage
from chinatxtbook.models.task import TaskKind as TaskKind
from chinatxtbook.models.task import TaskProgress as TaskProgress
from chinatxtbook.models.events import AppEvent as AppEvent
from chinatxtbook.models.errors import ErrorCode as ErrorCode
from chinatxtbook.models.errors import DomainError as DomainError
