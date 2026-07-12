"""Async workers for background tasks (download, merge, update).

Textual Workers run background tasks without blocking the UI event loop.
CPU-bound work (merge, hash) runs via asyncio.to_thread().
"""

import asyncio
import time
from typing import Optional

from chinatxtbook.config import DEFAULT_WORKERS
from chinatxtbook.core.downloader import DownloadOrchestrator
from chinatxtbook.core.git_client import GitClient
from chinatxtbook.core.state import StateManager
from chinatxtbook.ui.messages import (
    BookStatusChanged, DownloadProgress, PipelineStarted, PipelineCompleted,
)


class PipelineWorker:
    """Manages the download pipeline as background tasks.

    Coordinates: checkout → scan → verify → merge with live progress updates.
    """

    def __init__(self, app):
        self.app = app
        self._interrupted = False
        self._orchestrator: Optional[DownloadOrchestrator] = None

    async def run(self, selected_books: list) -> None:
        """Run the full download pipeline for selected books."""
        total = len(selected_books)
        self.app.post_message(PipelineStarted(total_books=total))

        # Initialize orchestrator
        git = self.app.git_client
        state_mgr = self.app.state_mgr
        self._orchestrator = DownloadOrchestrator(
            git_client=git,
            state_manager=state_mgr,
            log_callback=self._log,
        )

        success_count = 0
        fail_count = 0
        skip_count = 0

        for i, book in enumerate(selected_books):
            if self._interrupted:
                break

            key = book.get("key", str(i))
            self.app.post_message(BookStatusChanged(key, "downloading", ""))

            try:
                # Offload CPU-bound work to thread pool
                result = await asyncio.to_thread(
                    self._process_book, book
                )
                if result == "ok":
                    success_count += 1
                    self.app.post_message(BookStatusChanged(key, "verified"))
                elif result == "skipped":
                    skip_count += 1
                    self.app.post_message(BookStatusChanged(key, "verified"))
                else:
                    fail_count += 1
                    self.app.post_message(BookStatusChanged(key, "failed", str(result)))

            except Exception as e:
                fail_count += 1
                self.app.post_message(BookStatusChanged(key, "failed", str(e)))

            # Update progress
            pct = ((i + 1) / total) * 100
            self.app.post_message(DownloadProgress(
                overall_pct=pct,
                done_count=i + 1,
                total_count=total,
                current_file=book.get("name", ""),
            ))

        self.app.post_message(PipelineCompleted(
            success_count=success_count,
            fail_count=fail_count,
            skip_count=skip_count,
        ))

    def _process_book(self, book: dict) -> str:
        """Process a single book (runs in thread pool)."""
        time.sleep(0.5)  # Placeholder — Phase 4 integration
        return "ok"

    def _log(self, msg: str, level: str = "INFO") -> None:
        """Log callback forwarded to UI."""
        from chinatxtbook.ui.messages import LogMessage
        self.app.post_message(LogMessage(level=level, message=msg))

    def cancel(self) -> None:
        """Request graceful cancellation."""
        self._interrupted = True
