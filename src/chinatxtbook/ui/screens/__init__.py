"""Screen definitions for ChinaTextbook v1.1 TUI.

9 screens matching design doc 02/03:
  SCR-BROWSE    — main browsing interface (default)
  OVL-SEARCH    — global search overlay (/)
  SCR-SELECTED  — selected books panel (F2)
  OVL-CONFIRM   — download confirmation overlay (F5)
  SCR-TASKS     — task manager (F6)
  SCR-LOGS      — log viewer (F8)
  SCR-UPDATES   — software & textbook updates (F9)
  SCR-HELP      — help & diagnostics (F1)
  OVL-DETAIL    — book detail overlay (Enter)
"""

from chinatxtbook.ui.screens.browse import BrowseScreen
from chinatxtbook.ui.screens.selected import SelectedScreen
from chinatxtbook.ui.screens.tasks import TasksScreen
from chinatxtbook.ui.screens.logs import LogsScreen
from chinatxtbook.ui.screens.updates import UpdatesScreen
from chinatxtbook.ui.screens.help import HelpScreen
from chinatxtbook.ui.screens.search_overlay import SearchOverlay
from chinatxtbook.ui.screens.confirm_overlay import ConfirmOverlay
from chinatxtbook.ui.screens.detail_overlay import DetailOverlay

__all__ = [
    "BrowseScreen",
    "SelectedScreen",
    "TasksScreen",
    "LogsScreen",
    "UpdatesScreen",
    "HelpScreen",
    "SearchOverlay",
    "ConfirmOverlay",
    "DetailOverlay",
]
