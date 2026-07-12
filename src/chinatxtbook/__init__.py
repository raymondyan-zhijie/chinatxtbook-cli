"""ChinaTextbook - Chinese textbook PDF batch downloader with Textual TUI."""

__version__ = "1.1.0"
VERSION = __version__
# v1.0 is NOT compatible — see FR-020: migration must clear old selected_paths
# and prompt user to re-select
COMPATIBLE_STATE_VERSIONS = {"4.1", "4.2", "4.3", "1.1", "1.1.0"}
MIGRATABLE_STATE_VERSIONS = {"1.0"}
