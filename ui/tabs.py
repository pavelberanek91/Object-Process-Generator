from PySide6.QtWidgets import QTabBar, QMenu
from PySide6.QtCore import Signal

class RenameableTabBar(QTabBar):
    """TabBar, který vyvolá přejmenování na dvojklik a přes kontextové menu."""
    renameRequested = Signal(int)  # index tabu

    def mouseDoubleClickEvent(self, event):
        idx = self.tabAt(event.pos())
        if idx != -1:
            self.renameRequested.emit(idx)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        idx = self.tabAt(event.pos())
        if idx == -1:
            return
        menu = QMenu(self)
        act_rename = menu.addAction("Rename")
        # Případně by šlo přidat i "Close Tab" apod.
        chosen = menu.exec(event.globalPos())
        if chosen == act_rename:
            self.renameRequested.emit(idx)