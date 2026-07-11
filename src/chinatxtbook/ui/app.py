"""ChinaTextbook Textual TUI Application.

Three-panel layout with catalog tree, book list, and details panel.
"""


def run_app() -> int:
    """Launch the Textual TUI application."""
    try:
        from textual.app import App
    except ImportError:
        print(
            "Textual framework not installed.\n"
            "Install with: pip install textual>=0.52.0\n"
            "Or use CLI mode: python -m chinatxtbook --cli"
        )
        return 1

    # TODO: Phase 2 - Full TUI implementation
    print(
        "ChinaTextbook TUI mode (Phase 2 - under development)\n"
        "Please use CLI mode for now: python -m chinatxtbook --cli"
    )
    return 0
