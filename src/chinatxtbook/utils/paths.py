"""Path safety utilities — per design doc 2.2 Section 17, 2.3 Section 19.

All external paths MUST pass through PathPolicy before write operations.
Rejects: .. traversal, absolute paths, symlinks, NUL bytes.
"""

from pathlib import Path
from typing import Optional


class PathPolicy:
    """Validates and resolves paths within allowed root directories."""

    @staticmethod
    def resolve_within(root: Path, candidate: str) -> Optional[Path]:
        """Resolve candidate path and verify it stays within root.

        Returns the resolved Path if safe, None if rejected.

        Security invariants (2.2 Section 17):
        - Reject .. traversal (path traversal)
        - Reject absolute path injection
        - Reject NUL bytes
        - Reject symlinks escaping root
        """
        if not candidate:
            return None
        if "\0" in candidate:
            return None
        if candidate.startswith("/") or candidate.startswith("\\"):
            return None  # Absolute path injection

        try:
            candidate_path = Path(candidate)
            # Resolve to canonical form
            resolved = (root / candidate_path).resolve()
        except (OSError, ValueError, RuntimeError):
            return None

        # Check containment: resolved must be inside root
        try:
            resolved.relative_to(root)
        except ValueError:
            return None

        # Check for symlinks
        if resolved.is_symlink():
            return None
        # Check parents for symlinks
        for parent in resolved.parents:
            if parent.is_symlink():
                return None

        return resolved

    @staticmethod
    def safe_write_path(output_dir: Path, rel_path: str) -> Optional[Path]:
        """Validate and create parent dirs for a write target.
        Returns the safe resolved Path or None."""
        result = PathPolicy.resolve_within(output_dir, rel_path)
        if result:
            result.parent.mkdir(parents=True, exist_ok=True)
        return result
