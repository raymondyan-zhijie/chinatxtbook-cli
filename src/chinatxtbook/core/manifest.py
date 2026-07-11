"""Split-file manifest detection extracted from v1.0.

Builds expected PDF split-group manifests from Git tree output.
Source: v1.0 lines 566, 783-857.
"""

import os
import re
from pathlib import Path
from typing import Optional

# Split file pattern: "filename.pdf.1", "filename.PDF.2", etc.
# Source: v1.0 line 566.
SPLIT_RE = re.compile(r"(.+\.pdf)\.(\d+)$", re.IGNORECASE)


class SplitManifest:
    """Builds and queries expected split-file manifests from Git tree data."""

    @staticmethod
    def find_split_groups(dir_path: Path) -> dict:
        """Scan workspace dir for split files. Returns {base: {idx: [filenames]}}.

        Source: v1.0 lines 784-797.
        """
        groups = {}
        try:
            entries = list(dir_path.iterdir())
        except OSError:
            return {}
        for f in entries:
            if not f.is_file():
                continue
            m = SPLIT_RE.match(f.name)
            if m:
                groups.setdefault(m.group(1), {}).setdefault(
                    int(m.group(2)), []
                ).append(f.name)
        return groups

    @staticmethod
    def missing_parts(idxs) -> list:
        """Return sorted list of missing indices. Source: v1.0 lines 799-802."""
        if not idxs:
            return []
        return sorted(set(range(1, max(idxs) + 1)) - set(idxs))

    @staticmethod
    def build_expected_manifest(
        git_ls_tree_output: str, selected_paths: list[str]
    ) -> Optional[dict]:
        """Build expected split-file manifest from git ls-tree output.

        Returns {rel_dir(posix): {base: {idx: filename}}} or None on failure.
        Empty output (no split files) returns empty dict, not None.
        Source: v1.0 lines 804-829.
        """
        if git_ls_tree_output is None:
            return None

        manifest = {}
        for line in git_ls_tree_output.splitlines():
            line = line.strip()
            if not line:
                continue
            name = os.path.basename(line)
            m = SPLIT_RE.match(name)
            if not m:
                continue
            rel_dir = str(Path(line).parent.as_posix())
            base, idx = m.group(1), int(m.group(2))
            slot = manifest.setdefault(rel_dir, {}).setdefault(base, {})
            if idx in slot:
                slot[idx] = (
                    slot[idx] if isinstance(slot[idx], list) else [slot[idx]]
                ) + [name]
            else:
                slot[idx] = name
        return manifest

    @staticmethod
    def clean_stale_tmp(dir_path: Path):
        """Remove only *.pdf.tmp files, not other .tmp files.
        Source: v1.0 lines 831-838.
        """
        try:
            for f in dir_path.iterdir():
                if f.is_file() and f.name.lower().endswith(".pdf.tmp"):
                    f.unlink(missing_ok=True)
        except OSError:
            pass
