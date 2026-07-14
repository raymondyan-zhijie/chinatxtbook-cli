"""Configuration constants for ChinaTextbook v1.1.

Extracted from v1.0 lines 106-128. Single-source (GitHub only) per v1.1 design.
"""

import os
from pathlib import Path

VERSION = "1.1.0"

# Fixed repository source (v1.1: single source, no multi-source switching)
GITHUB_REPO = "https://github.com/TapXWorld/ChinaTextbook.git"

# Workspace and state files (F-11: overridable via env vars for non-cwd runs)
WORK_DIR = Path(os.environ.get("CHINATXTBOOK_WORK_DIR", "ChinaTextbook_Workspace"))
OUTPUT_DIR = Path(os.environ.get("CHINATXTBOOK_OUTPUT_DIR", "ChinaTextbook_Output"))
STATE_FILE = Path(os.environ.get("CHINATXTBOOK_STATE_FILE", "china_textbook_state.json"))
LOG_FILE = Path(os.environ.get("CHINATXTBOOK_LOG_FILE", "china_textbook.log"))
REPORT_FILE = Path(os.environ.get("CHINATXTBOOK_REPORT_FILE", "china_textbook_report.md"))

# Chunk size for file I/O (1 MB)
CHUNK_SIZE = 1024 * 1024

# Concurrency
DEFAULT_WORKERS = 2
MAX_WORKERS = 8

# Default top-level directories to show in catalog
DEFAULT_TOP_DIRS = ["小学", "初中", "高中"]

# Log rotation threshold (5 MB)
LOG_MAX_BYTES = 5 * 1024 * 1024

# Proxy configuration (uncomment as needed)
# os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
