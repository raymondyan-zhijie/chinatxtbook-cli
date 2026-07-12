"""Task state machine models per design doc 2.4 Sections 5-6."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskState(str, Enum):
    pending = "pending"
    running = "running"
    cancelling = "cancelling"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    interrupted = "interrupted"


class TaskStage(str, Enum):
    queued = "queued"
    preflight = "preflight"
    fetch = "fetch"
    checkout = "checkout"
    merge = "merge"
    verify = "verify"
    cleanup = "cleanup"
    persist = "persist"
    done = "done"


class TaskKind(str, Enum):
    catalog_refresh = "catalog_refresh"
    download = "download"
    verify = "verify"
    update_check = "update_check"
    repository_update = "repository_update"
    diagnostic = "diagnostic"


@dataclass
class TaskProgress:
    completed_units: int = 0
    total_units: int = 0
    bytes_done: int = 0
    bytes_total: int = 0
    estimated: bool = False
    message: str = ""


@dataclass
class TaskRecord:
    task_id: str
    kind: TaskKind = TaskKind.download
    state: TaskState = TaskState.pending
    stage: TaskStage = TaskStage.queued
    book_ids: list = field(default_factory=list)
    cancel_requested: bool = False
    progress: TaskProgress = field(default_factory=TaskProgress)
    error: Optional[str] = None
