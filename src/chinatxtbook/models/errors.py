"""Stable error codes per design doc 2.2 Section 14.1."""

from dataclasses import dataclass, field


class ErrorCode:
    ENV_GIT_MISSING = "ENV-GIT-MISSING"
    ENV_DISK_LOW = "ENV-DISK-LOW"
    REPO_REMOTE_MISMATCH = "REPO-REMOTE-MISMATCH"
    REPO_FETCH_FAILED = "REPO-FETCH-FAILED"
    CAT_MISSING_PART = "CAT-MISSING-PART"
    CAT_DUPLICATE_BOOK = "CAT-DUPLICATE-BOOK"
    DL_PATH_MISSING = "DL-PATH-MISSING"
    DL_CANCELLED = "DL-CANCELLED"
    MERGE_INPUT_CHANGED = "MERGE-INPUT-CHANGED"
    MERGE_WRITE_FAILED = "MERGE-WRITE-FAILED"
    VERIFY_HASH_MISMATCH = "VERIFY-HASH-MISMATCH"
    STATE_CORRUPT = "STATE-CORRUPT"
    STATE_MIGRATION_FAILED = "STATE-MIGRATION-FAILED"
    UPDATE_CHECK_FAILED = "UPDATE-CHECK-FAILED"


@dataclass
class DomainError(Exception):
    error_code: str
    message: str = ""
    recoverable: bool = False
    context: dict = field(default_factory=dict)
