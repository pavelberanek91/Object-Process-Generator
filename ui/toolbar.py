"""Toolbar a související funkce pro OPM Editor."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QToolBar,
    QToolButton,
    QMenu,
    QComboBox,
    QLabel,
    QWidget,
    QSizePolicy,
    QStyle,
)
from constants import Mode, LINK_TYPES
from ui.icons import icon_shape, icon_std
from persistence.json_io import save_scene_as_json, load_scene_from_json


class ToolbarManager:
    """Manager pro správu toolbarů aplikace."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.actions = {}
    
    def create_all_toolbars(self):
        """Vytvoří všechny toolbary aplikace."""
        self._create_main_toolbar()
        self._create_edit_toolbar()
    
    def _create_main_toolbar(self):
        """Vytvoří hlavní toolbar."""
        tb = QToolBar("Tools")
        self.main_window.addToolBar(Qt.TopToolBarArea, tb)
        
        # File menu
        self._add_file_menu(tb)
        
        tb.addSeparator()
        
        # Out-zoom button (viditelné pouze v in-zoom módu)
        self.main_window.act_out_zoom = self._add_icon_btn(
            tb,
            icon_shape("zoom_out"),
            "Back to Parent (Out-zoom)",
            lambda: self.main_window.navigate_to_parent()
        )
        self.main_window.act_out_zoom.setVisible(False)  # Zpočátku skryté
        
        tb.addSeparator()
        self._add_btn(tb, "Create OPL", lambda: self.main_window.import_opl_dialog())
        tb.addSeparator()
        self._add_btn(tb, "Generate OPL", lambda: self.main_window.open_nl_to_opl_dialog())
        
        tb.addSeparator()
        self._add_export_menu(tb)
        
        self._add_spacing(tb, 16)
        
        # Mode actions
        self._add_mode_actions(tb)
        
        # Other actions
        tb.addSeparator()
        self._add_icon_btn(
            tb, 
            icon_shape("delete"), 
            "Delete (Del)", 
            lambda: self.main_window.delete_selected()
        )
        tb.addSeparator()
        self._add_icon_btn(
            tb,
            icon_std(self.main_window, QStyle.SP_DialogDiscardButton),
            "Clear All",
            lambda: self.main_window.clear_all()
        )
        tb.addSeparator()
        self._add_icon_btn(
            tb,
            icon_shape("zoom_in"),
            "Zoom In (Ctrl + Wheel)",
            lambda: self.main_window.zoom_in()
        )
        tb.addSeparator()
        self._add_icon_btn(
            tb,
            icon_shape("zoom_out"),
            "Zoom Out (Ctrl + Wheel)",
            lambda: self.main_window.zoom_out()
        )
        tb.addSeparator()
        self._add_icon_btn(
            tb,
            icon_shape("reset_zoom"),
            "Reset Zoom",
            lambda: self.main_window.zoom_reset()
        )
    
    def _create_edit_toolbar(self):
        """Vytvoří edit toolbar s undo/redo."""
        tb = self.main_window.addToolBar("Edit")
        act_undo = self.main_window.undo_stack.createUndoAction(self.main_window, "Undo")
        act_redo = self.main_window.undo_stack.createRedoAction(self.main_window, "Redo")
        tb.addAction(act_undo)
        tb.addAction(act_redo)
        act_undo.setShortcut("Ctrl+Z")
        act_redo.setShortcut("Ctrl+Y")
    
    def _add_file_menu(self, tb: QToolBar):
        """Přidá File menu do toolbaru."""
        file_menu = QMenu("File", self.main_window)
        file_menu.addAction("New OPD", lambda: self.main_window._new_canvas())
        file_menu.addSeparator()
        file_menu.addAction(
            "Export OPD",
            lambda: save_scene_as_json(self.main_window.scene, self.main_window._current_tab_title())
        )
        file_menu.addAction(
            "Import OPD (Current Tab)",
            lambda: load_scene_from_json(
                self.main_window.scene,
                self.main_window.allowed_link,
                new_canvas_callback=self.main_window._new_canvas,
                new_tab=False
            )
        )
        file_menu.addAction(
            "Import OPD (New Tab)",
            lambda: load_scene_from_json(
                self.main_window.scene,
                self.main_window.allowed_link,
                new_canvas_callback=self.main_window._new_canvas,
                new_tab=True
            )
        )
        file_menu.addSeparator()
        file_menu.addAction(
            "Rename OPD",
            lambda: self.main_window._rename_tab(self.main_window.tabs.currentIndex())
        )
        file_menu.addAction("Close Tab", lambda: self.main_window._close_current_tab())
        file_menu.addSeparator()
        file_menu.addAction("Exit", QApplication.instance().quit)
        
        file_btn = QToolButton()
        file_btn.setText("File")
        file_btn.setMenu(file_menu)
        file_btn.setPopupMode(QToolButton.InstantPopup)
        file_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tb.addWidget(file_btn)
    
    def _add_export_menu(self, tb: QToolBar):
        """Přidá Export menu do toolbaru."""
        export_menu = QMenu("Image", self.main_window)
        export_menu.addAction("Save as JPG", lambda: self.main_window.export_image("jpg"))
        export_menu.addAction("Save as PNG", lambda: self.main_window.export_image("png"))
        export_menu.addAction("Save as SVG", lambda: self.main_window.export_image("svg"))
        
        export_btn = QToolButton()
        export_btn.setText("Image")
        export_btn.setMenu(export_menu)
        export_btn.setPopupMode(QToolButton.InstantPopup)
        export_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tb.addWidget(export_btn)
    
    def _add_mode_actions(self, tb: QToolBar):
        """Přidá akce pro přepínání módů."""
        act_select = QAction(icon_shape("cursor"), "", self.main_window)
        act_select.setToolTip("Select/Move")
        act_select.setCheckable(True)
        tb.addAction(act_select)
        act_select.triggered.connect(lambda: self.main_window.set_mode(Mode.SELECT))
        
        tb.addSeparator()
        act_obj = self._add_icon_btn(
            tb,
            icon_shape("object"),
            "Add Object",
            lambda: self.main_window.set_mode(Mode.ADD_OBJECT),
            checkable=True
        )
        
        tb.addSeparator()
        act_proc = self._add_icon_btn(
            tb,
            icon_shape("process"),
            "Add Process",
            lambda: self.main_window.set_mode(Mode.ADD_PROCESS),
            checkable=True
        )
        
        tb.addSeparator()
        act_state = self._add_icon_btn(
            tb,
            icon_shape("state"),
            "Add State",
            lambda: self.main_window.set_mode(Mode.ADD_STATE),
            checkable=True
        )
        
        tb.addSeparator()
        act_link = self._add_icon_btn(
            tb,
            icon_shape("link"),
            "Add Link",
            lambda: self.main_window.set_mode(Mode.ADD_LINK),
            checkable=True
        )
        
        # Combo pro default link type
        self.main_window.cmb_default_link_type = QComboBox()
        
        # Přidej procedurální linky
        self.main_window.cmb_default_link_type.addItem("─── Procedural ───")
        self.main_window.cmb_default_link_type.model().item(0).setEnabled(False)
        self.main_window.cmb_default_link_type.addItems([
            "input", "output", "consumption", "result", "effect", "agent", "instrument"
        ])
        
        # Přidej oddělovač a strukturální linky
        self.main_window.cmb_default_link_type.insertSeparator(8)
        self.main_window.cmb_default_link_type.addItem("─── Structural ───")
        self.main_window.cmb_default_link_type.model().item(9).setEnabled(False)
        self.main_window.cmb_default_link_type.addItems([
            "aggregation", "exhibition", "generalization", "instantiation"
        ])
        
        self.main_window.cmb_default_link_type.setCurrentText(self.main_window.default_link_type)
        self.main_window.cmb_default_link_type.currentTextChanged.connect(
            lambda text: setattr(self.main_window, "default_link_type", text) if "───" not in text else None
        )
        tb.addWidget(QLabel("Default Link:"))
        tb.addWidget(self.main_window.cmb_default_link_type)
        
        # Group pro exkluzivní výběr
        group = QActionGroup(self.main_window)
        group.setExclusive(True)
        for a in (act_select, act_obj, act_proc, act_state, act_link):
            group.addAction(a)
        act_select.setChecked(True)
        
        # Uložit akce pro pozdější použití
        self.actions = {
            Mode.SELECT: act_select,
            Mode.ADD_OBJECT: act_obj,
            Mode.ADD_PROCESS: act_proc,
            Mode.ADD_STATE: act_state,
            Mode.ADD_LINK: act_link
        }
        self.main_window.actions = self.actions
    
    def _add_btn(self, tb: QToolBar, title: str, slot, checkable=False):
        """Přidá jednoduché tlačítko do toolbaru."""
        act = QAction(title, self.main_window)
        act.triggered.connect(slot)
        tb.addAction(act)
        act.setCheckable(checkable)
        return act
    
    def _add_icon_btn(self, tb: QToolBar, icon, tooltip: str, slot, checkable=False):
        """Přidá tlačítko s ikonou do toolbaru."""
        act = QAction(icon, "", self.main_window)
        act.setToolTip(tooltip)
        act.setStatusTip(tooltip)
        act.triggered.connect(slot)
        act.setCheckable(checkable)
        tb.addAction(act)
        return act
    
    @staticmethod
    def _add_spacing(tb: QToolBar, width: int = 16):
        """Přidá mezeru do toolbaru."""
        spacer = QWidget()
        spacer.setFixedWidth(width)
        spacer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        return spacer

