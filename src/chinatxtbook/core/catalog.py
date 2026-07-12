"""Hierarchical catalog builder for v1.1.

Builds a 4-level bibliographic tree from Git ls-tree output:
学段(stage) → 科目(subject) → 年级/册次(grade) → 教材(book)

Replaces v1.0's flat directory listing with hierarchical navigation.
Source: v1.0 lines 565-652 (size fetching), new hierarchy logic.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from chinatxtbook.core.git_client import GitClient
from chinatxtbook.utils.format import fmt_size


@dataclass
class BookEntry:
    """A single textbook (leaf node in the catalog tree)."""
    key: str                    # POSIX path like "小学/语文/人教版/一年级/语文上.pdf"
    name: str                   # Display name
    stage: str                  # 学段
    subject: str                # 科目
    grade: str                  # 年级/册次
    part_count: int = 0         # Number of split parts
    total_size: int = 0         # Total bytes from size cache
    is_selected: bool = False   # UI selection state


@dataclass
class CatalogNode:
    """A node in the bibliographic hierarchy."""
    name: str
    display_name: str
    path: str                   # POSIX path in repo
    level: str                  # "stage" | "subject" | "grade" | "book"
    children: list = field(default_factory=list)
    size_bytes: int = 0
    book_count: int = 0
    is_expanded: bool = False


class CatalogBuilder:
    """Build the 4-level bibliographic tree from repository metadata.

    Parses git ls-tree output to extract:
    小学/语文/人教版/一年级/语文一年级上册.pdf.1 → stage=小学, subject=语文, grade=一年级
    """

    STAGE_ORDER = [
        "小学", "初中", "高中", "大学",
        "小学（五•四学制）", "初中（五•四学制）",
    ]

    def __init__(self, git_client: GitClient):
        self.git = git_client

    def build_tree(
        self,
        selected_paths: list[str],
        size_cache: Optional[dict] = None,
    ) -> list[CatalogNode]:
        """Build the top-level catalog tree (stages).

        Args:
            selected_paths: Top-level directories to include.
            size_cache: Optional {path: size_bytes} from API.

        Returns:
            List of stage-level CatalogNode objects.
        """
        stages: dict[str, CatalogNode] = {}
        dirs = size_cache.get("dirs", {}) if size_cache else {}

        for path in selected_paths:
            parts = path.rstrip("/").split("/")
            stage_name = parts[0]

            if stage_name not in stages:
                stages[stage_name] = CatalogNode(
                    name=stage_name,
                    display_name=stage_name,
                    path=stage_name,
                    level="stage",
                    size_bytes=dirs.get(stage_name, 0),
                )

            if len(parts) >= 2:
                subject_name = parts[1]
                stage_node = stages[stage_name]
                existing = {c.name: c for c in stage_node.children}
                if subject_name not in existing:
                    child_path = f"{stage_name}/{subject_name}"
                    child = CatalogNode(
                        name=subject_name,
                        display_name=subject_name,
                        path=child_path,
                        level="subject",
                        size_bytes=dirs.get(child_path, 0),
                    )
                    stage_node.children.append(child)
                else:
                    child = existing[subject_name]

                # Further nesting (grade level)
                if len(parts) >= 3:
                    grade_name = parts[2]
                    grade_path = f"{stage_name}/{subject_name}/{grade_name}"
                    sub_existing = {c.name: c for c in child.children}
                    if grade_name not in sub_existing:
                        grade_node = CatalogNode(
                            name=grade_name,
                            display_name=grade_name,
                            path=grade_path,
                            level="grade",
                            size_bytes=dirs.get(grade_path, 0),
                        )
                        child.children.append(grade_node)

        # Sort stages by preferred order
        result = []
        for stage_name in self.STAGE_ORDER:
            if stage_name in stages:
                result.append(stages[stage_name])
        # Add any stages not in the preferred order
        for name, node in stages.items():
            if name not in self.STAGE_ORDER:
                result.append(node)

        # Sort children within each node
        for node in result:
            node.children.sort(key=lambda c: c.name)
            for child in node.children:
                child.children.sort(key=lambda c: c.name)

        return result

    def get_books(
        self,
        stage: str,
        subject: Optional[str] = None,
        grade: Optional[str] = None,
    ) -> list[BookEntry]:
        """Get books under a catalog node.

        Uses git ls-tree to enumerate all split files in the path.
        """
        from chinatxtbook.core.manifest import SPLIT_RE

        path = stage
        if subject:
            path = f"{stage}/{subject}"
        if grade:
            path = f"{stage}/{subject}/{grade}"

        files = self.git.ls_tree(path, recursive=True) or []

        # Group split files by base name
        books: dict[str, BookEntry] = {}
        for file_path in files:
            name = os.path.basename(file_path)
            m = SPLIT_RE.match(name)
            if not m:
                continue
            base = m.group(1)
            idx = int(m.group(2))
            rel_dir = str(Path(file_path).parent.as_posix())

            if base not in books:
                # Parse hierarchy from path
                parts = rel_dir.split("/")
                st = parts[0] if len(parts) > 0 else ""
                sub = parts[1] if len(parts) > 1 else ""
                grd = parts[2] if len(parts) > 2 else ""

                books[base] = BookEntry(
                    key=f"{rel_dir}/{base}",
                    name=f"{os.path.basename(rel_dir)}/{base}"
                    if len(parts) > 2 else base,
                    stage=st,
                    subject=sub,
                    grade=grd,
                    part_count=0,
                )

            books[base].part_count = max(books[base].part_count, idx)

        return sorted(books.values(), key=lambda b: b.name)
