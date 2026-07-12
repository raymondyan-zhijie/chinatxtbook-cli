"""Entry point for ChinaTextbook v1.1.

Supports both TUI mode (default) and CLI mode (--cli flag for headless/automated use).
"""

import argparse
import sys


def main():
    """Main entry point. Parses args and launches TUI or CLI mode."""
    parser = argparse.ArgumentParser(
        description=f"ChinaTextbook 下载与合并 v{__import__('chinatxtbook').__version__}"
    )
    parser.add_argument(
        "--cli", action="store_true",
        help="Run in CLI mode (headless, compatible with v1.0 arguments)"
    )
    parser.add_argument(
        "--version", action="version",
        version=f"v{__import__('chinatxtbook').__version__}"
    )
    # Parse only known args; pass remaining to CLI or TUI handler
    args, remaining = parser.parse_known_args()

    if args.cli:
        from chinatxtbook.cli import run_cli
        return run_cli(remaining)

    # Default: TUI mode
    from chinatxtbook.utils.platform import setup_console, setup_interrupt_handler
    setup_console()
    setup_interrupt_handler()
    from chinatxtbook.ui.app import run_app
    return run_app()


if __name__ == "__main__":
    sys.exit(main())
