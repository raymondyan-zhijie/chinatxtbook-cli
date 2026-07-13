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
        """
        if not candidate:
            return None
        if "\0" in candidate:
            return None
        if candidate.startswith("/") or candidate.startswith("\\"):
            return None

        try:
            # N-2: Resolve root first so relative_to works correctly
            resolved_root = root.resolve()
            resolved = (resolved_root / candidate).resolve()
        except (OSError, ValueError, RuntimeError):
            return None

        # Check containment: resolved must be inside resolved root
        try:
            resolved.relative_to(resolved_root)
        except ValueError:
            return None

        # Check for symlinks (must be done BEFORE resolve for correct detection)
        candidate_path = resolved_root / Path(candidate)
        parts = list(candidate_path.parents) + [candidate_path]
        for part in parts:
            try:
                if part.is_symlink():
                    return None
            except OSError:
                return None

        return resolved

    @staticmethod
    def safe_write_path(output_dir: Path, rel_path: str) -> Optional[Path]:
        """Validate and create parent dirs for a write target."""
        result = PathPolicy.resolve_within(output_dir, rel_path)
        if result:
            result.parent.mkdir(parents=True, exist_ok=True)
        return result
