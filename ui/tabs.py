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
        act_close = menu.addAction("Close Tab")
        chosen = menu.exec(event.globalPos())
        if chosen == act_rename:
            self.renameRequested.emit(idx)
        elif chosen == act_close:
            # Zavolá close tab na parent widget (QTabWidget)
            parent_tab_widget = self.parent()
            if parent_tab_widget and hasattr(parent_tab_widget, 'parent'):
                main_window = parent_tab_widget.parent()
                if main_window and hasattr(main_window, '_close_tab_at_index'):
                    main_window._close_tab_at_index(idx)