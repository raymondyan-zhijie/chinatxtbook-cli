"""OVL-DETAIL - Book detail overlay (Enter).

Shows complete metadata for a focused book:
full path, part sizes, SHA256, status history.
"""

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Button

from chinatxtbook.utils.format import fmt_size


class DetailOverlay(ModalScreen):
    """OVL-DETAIL: Full book metadata overlay.

    Activated by Enter on a book in the catalog tree or book list.
    Shows complete file information and part breakdown.
    """

    BINDINGS = [
        ("escape", "dismiss", "关闭"),
    ]

    def __init__(self, book_data: Optional[dict] = None, **kwargs):
        super().__init__(**kwargs)
        self.book_data = book_data or {}

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-overlay"):
            yield Static("📄 教材详情", classes="modal-title")
            yield Static("", id="detail-full-content", classes="modal-content")
            yield Button("关闭 (Esc)", variant="default", id="detail-close")

    def on_mount(self) -> None:
        content = self.query_one("#detail-full-content", Static)
        d = self.book_data

        lines = [
            f"📖 名称: {d.get('name', d.get('base', 'N/A'))}",
            f"📐 分卷数: {d.get('part_count', d.get('parts', '?'))} 卷",
            f"💾 总大小: {fmt_size(d.get('size', 0))}",
            f"📊 状态: {d.get('status', '未下载')}",
            f"📁 路径: {d.get('path', d.get('key', 'N/A'))}",
            "",
            "━━ 各分卷详情 ━━",
        ]

        parts = d.get("parts", {})
        if isinstance(parts, dict):
            for idx in sorted(parts):
                p = parts[idx]
                p_name = p[0] if isinstance(p, tuple) else p
                lines.append(f"  卷 {idx}: {p_name}")
        elif isinstance(parts, list):
            for i, p in enumerate(parts, 1):
                lines.append(f"  卷 {i}: {p}")
        else:
            lines.append("  (无分卷信息)")

        if d.get("sha256"):
            lines.append(f"\n🔐 SHA256: {d['sha256']}")

        content.update("\n".join(lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "detail-close":
            self.dismiss()

    async def action_dismiss(self, result: object = None) -> None:
        self.dismiss(result)
