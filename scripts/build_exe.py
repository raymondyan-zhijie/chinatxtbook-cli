"""PyInstaller build script for ChinaTextbook Windows EXE."""
import PyInstaller.__main__
from pathlib import Path

PyInstaller.__main__.run([
    '--name=ChinaTextbook',
    '--onefile',
    '--console',
    '--add-data=src/chinatxtbook/ui/styles.tcss:chinatxtbook/ui',
    '--collect-all=textual',
    '--hidden-import=textual.widgets',
    '--hidden-import=textual.containers',
    '--hidden-import=textual.app',
    '--hidden-import=textual.css',
    '--hidden-import=rich',
    'src/chinatxtbook/__main__.py',
])
