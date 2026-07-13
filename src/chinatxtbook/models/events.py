"""Application events per design doc 2.4 Section 19."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AppEvent:
    """Base class for all application events."""
    pass


@dataclass(frozen=True)
class TaskStateChanged(AppEvent):
    task_id: str = ""
    old_state: str = ""
    new_state: str = ""
    stage: str = ""


@dataclass(frozen=True)
class TaskProgressed(AppEvent):
    task_id: str = ""
    progress: float = 0.0
    message: str = ""


@dataclass(frozen=True)
class TaskCompleted(AppEvent):
    task_id: str = ""
    success_count: int = 0
    fail_count: int = 0


@dataclass(frozen=True)
class TaskFailed(AppEvent):
    task_id: str = ""
    error_code: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class SelectionChanged(AppEvent):
    selected_count: int = 0
    estimated_size: int = 0


@dataclass(frozen=True)
class CatalogChanged(AppEvent):
    book_count: int = 0
