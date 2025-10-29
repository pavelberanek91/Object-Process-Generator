"""Custom tab bar s podporou přejmenování tabů.

Umožňuje uživateli přejmenovat tab dvojklikem nebo přes kontextové menu (pravé tlačítko).
"""
from PySide6.QtWidgets import QTabBar, QMenu
from PySide6.QtCore import Signal


class RenameableTabBar(QTabBar):
    """
    TabBar s podporou přejmenování tabů.
    
    Emituje signál renameRequested(int) při dvojkliku nebo výběru z kontextového menu.
    """
    renameRequested = Signal(int)  # Index tabu k přejmenování

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