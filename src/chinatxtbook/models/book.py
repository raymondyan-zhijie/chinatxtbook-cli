"""Book and SourceFile models per design doc 2.3 Sections 5-6."""

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SourceKind(str, Enum):
    complete_pdf = "complete_pdf"
    split_part = "split_part"


def make_book_id(logical_path: str) -> str:
    """Generate stable BookId from logical path. 2.3 Section 5.3."""
    canonical = f"v1|{logical_path}"
    return "bk_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class SourceFile:
    """A single source file in the Git repository. 2.3 Section 6.1."""

    git_path: str
    kind: SourceKind
    part_number: Optional[int] = None  # null for complete_pdf, >=1 for split_part


@dataclass(frozen=True)
class Book:
    """A single textbook — may be one PDF or multiple split parts. 2.3 Section 6.2."""

    book_id: str
    logical_path: str
    title: str
    stage: str
    subject: str
    category_label: str = ""
    publisher: Optional[str] = None
    source_files: tuple = field(default_factory=tuple)
    expected_size_bytes: Optional[int] = None
    search_text: str = ""
    catalog_issues: tuple = field(default_factory=tuple)
