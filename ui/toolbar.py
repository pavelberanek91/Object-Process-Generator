"""Toolbar a související funkce pro OPM Editor."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QMouseEvent
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
    QSlider,
)
from constants import Mode, LINK_TYPES
from ui.icons import icon_shape, icon_std
from persistence.json_io import save_scene_as_json, load_scene_from_json


class ZoomSlider(QSlider):
    """Slider pro zoom s podporou dvojkliku pro reset na 100%."""
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._double_click_pending = False
    
    def mousePressEvent(self, event: QMouseEvent):
        """Zachytí stisk myši - pokud jde o dvojklik, ignoruj změnu hodnoty."""
        if self._double_click_pending:
            # Ignoruj tento press event, protože jde o druhou část dvojkliku
            self._double_click_pending = False
            event.accept()
            return
        # Normální zpracování
        super().mousePressEvent(event)
    
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Při dvojkliku nastaví hodnotu na 100%."""
        self._double_click_pending = True
        self.setValue(100)
        event.accept()  # Zabráníme dalšímu zpracování události


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
        
        # Mode actions
        self._add_mode_actions(tb)
        
        # Other actions
        tb.addSeparator()
        self._add_icon_btn(
            tb, 
            icon_std(self.main_window, QStyle.SP_TrashIcon), 
            "Delete (Del)", 
            lambda: self.main_window.delete_selected()
        )
        
        # Out-zoom button (viditelné pouze v in-zoom módu)
        self.main_window.act_out_zoom = self._add_icon_btn(
            tb,
            icon_shape("zoom_out"),
            "Back to Parent (Out-zoom)",
            lambda: self.main_window.navigate_to_parent()
        )
        self.main_window.act_out_zoom.setVisible(False)  # Zpočátku skryté
        
        tb.addSeparator()
        
        # Zoom slider
        zoom_label = QLabel("Zoom:")
        tb.addWidget(zoom_label)
        
        zoom_slider = ZoomSlider(Qt.Horizontal)
        zoom_slider.setMinimum(20)  # 20%
        zoom_slider.setMaximum(500)  # 500%
        zoom_slider.setValue(100)  # 100%
        zoom_slider.setTickPosition(QSlider.TicksBelow)
        zoom_slider.setTickInterval(50)
        zoom_slider.setFixedWidth(150)
        zoom_slider.setToolTip("Zoom (Ctrl + Wheel, dvojklik = reset na 100%)")
        zoom_slider.valueChanged.connect(lambda value: self.main_window.set_zoom(value / 100.0))
        tb.addWidget(zoom_slider)
        
        # Label s aktuální hodnotou zoomu
        self.main_window.zoom_value_label = QLabel("100%")
        self.main_window.zoom_value_label.setFixedWidth(45)
        tb.addWidget(self.main_window.zoom_value_label)
        
        # Uložit slider pro pozdější aktualizaci
        self.main_window.zoom_slider = zoom_slider
        
        # Menu (File, View, OPL, Image) jsou dostupná pouze v nativním menubaru, ne v toolbaru
        self._add_menu_to_menubar()
    
    def _add_menu_to_menubar(self):
        """Přidá menu pouze do nativního menubaru (ne do toolbaru)."""
        try:
            # File menu
            file_menu = self._create_file_menu()
            self.main_window.menuBar().addMenu(file_menu)
            
            # View menu
            view_menu = self._create_view_menu()
            self.main_window.menuBar().addMenu(view_menu)
            
            # OPL menu
            opl_menu = self._create_opl_menu()
            self.main_window.menuBar().addMenu(opl_menu)
            
            # Image menu
            image_menu = self._create_export_menu()
            self.main_window.menuBar().addMenu(image_menu)
        except Exception:
            pass
    
    def _create_edit_toolbar(self):
        """Vytvoří edit toolbar s undo/redo."""
        tb = self.main_window.addToolBar("Edit")
        act_undo = self.main_window.undo_stack.createUndoAction(self.main_window, "Undo")
        act_redo = self.main_window.undo_stack.createRedoAction(self.main_window, "Redo")
        tb.addAction(act_undo)
        tb.addAction(act_redo)
        act_undo.setShortcut("Ctrl+Z")
        act_redo.setShortcut("Ctrl+Y")
    
    def _create_file_menu(self):
        """Vytvoří File menu (pouze pro menubar)."""
        file_menu = QMenu("File", self.main_window)
        # New OPD - odstraněno: canvasy jsou teď automaticky vytvářeny pro zoom-in mechanismus
        
        # Export OPD
        act_export = QAction(self.main_window)
        act_export.setShortcut(QKeySequence("Ctrl+S"))
        act_export.setText("Export OPD")
        act_export.triggered.connect(
            lambda: save_scene_as_json(self.main_window.scene, self.main_window._current_tab_title(), self.main_window)
        )
        file_menu.addAction(act_export)

        # Import OPD
        act_import = QAction(self.main_window)
        act_import.setShortcut(QKeySequence("Ctrl+I"))
        act_import.setText("Import OPD")
        act_import.triggered.connect(
            lambda: load_scene_from_json(
                self.main_window.scene,
                self.main_window.allowed_link,
                new_canvas_callback=self.main_window._new_canvas,
                new_tab=False,
                main_window=self.main_window
            )
        )
        file_menu.addAction(act_import)

        file_menu.addSeparator()
        # Rename OPD - odstraněno: přejmenování se provádí přes pravý klik na název canvasu (procesu)
        # Close Tab - odstraněno: zavření se provádí přes pravý klik na název canvasu (procesu)

        # Exit
        act_exit = QAction(self.main_window)
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.setText("Exit")
        act_exit.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(act_exit)
        
        return file_menu
    
    def _create_export_menu(self):
        """Vytvoří Image menu (pouze pro menubar)."""
        export_menu = QMenu("Image", self.main_window)
        act_jpg = QAction(self.main_window)
        act_jpg.setShortcut(QKeySequence("Ctrl+Shift+J"))
        act_jpg.setText("Save as JPG")
        act_jpg.triggered.connect(lambda: self.main_window.export_image("jpg"))
        export_menu.addAction(act_jpg)

        act_png = QAction(self.main_window)
        act_png.setShortcut(QKeySequence("Ctrl+Shift+N"))  # N as iNage/PNG to avoid conflicts
        act_png.setText("Save as PNG")
        act_png.triggered.connect(lambda: self.main_window.export_image("png"))
        export_menu.addAction(act_png)

        act_svg = QAction(self.main_window)
        act_svg.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act_svg.setText("Save as SVG")
        act_svg.triggered.connect(lambda: self.main_window.export_image("svg"))
        export_menu.addAction(act_svg)
        
        return export_menu

    def _create_opl_menu(self):
        """Vytvoří OPL menu (pouze pro menubar)."""
        opl_menu = QMenu("OPL", self.main_window)
        
        # Import OPL
        act_import_opl = QAction(self.main_window)
        act_import_opl.setShortcut(QKeySequence("Ctrl+Shift+I"))
        act_import_opl.setText("Import OPL")
        act_import_opl.triggered.connect(lambda: self.main_window.import_opl_dialog())
        opl_menu.addAction(act_import_opl)
        
        # Generate OPL
        act_generate_opl = QAction(self.main_window)
        act_generate_opl.setShortcut(QKeySequence("Ctrl+Shift+G"))
        act_generate_opl.setText("Generate OPL")
        act_generate_opl.triggered.connect(lambda: self.main_window.open_nl_to_opl_dialog())
        opl_menu.addAction(act_generate_opl)
        
        opl_menu.addSeparator()
        
        # Export OPL
        act_export_opl = QAction(self.main_window)
        act_export_opl.setShortcut(QKeySequence("Ctrl+Shift+E"))
        act_export_opl.setText("Export OPL")
        act_export_opl.triggered.connect(lambda: self.main_window.preview_opl())
        opl_menu.addAction(act_export_opl)
        
        return opl_menu
    
    def _create_view_menu(self):
        """Vytvoří View menu (pouze pro menubar)."""
        view_menu = QMenu("View", self.main_window)
        
        # Toggle akce pro dock panely
        if hasattr(self.main_window, 'dock_hierarchy'):
            act_h = self.main_window.dock_hierarchy.toggleViewAction()
            act_h.setShortcut(QKeySequence("Ctrl+Shift+H"))
            act_h.setText("Hierarchie procesů")
            view_menu.addAction(act_h)
            self.main_window.addAction(act_h)  # umožní fungování zkratky globálně
        
        if hasattr(self.main_window, 'dock_props'):
            act_p = self.main_window.dock_props.toggleViewAction()
            act_p.setShortcut(QKeySequence("Ctrl+Shift+P"))
            act_p.setText("Properties")
            view_menu.addAction(act_p)
            self.main_window.addAction(act_p)
        
        if hasattr(self.main_window, 'dock_simulation'):
            act_s = self.main_window.dock_simulation.toggleViewAction()
            act_s.setShortcut(QKeySequence("Ctrl+Shift+M"))  # M jako Model/Simulation
            act_s.setText("Simulation")
            view_menu.addAction(act_s)
            self.main_window.addAction(act_s)
        
        return view_menu
    
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
            "Add Object (O)",
            lambda: self.main_window.set_mode(Mode.ADD_OBJECT),
            checkable=True
        )
        
        tb.addSeparator()
        act_proc = self._add_icon_btn(
            tb,
            icon_shape("process"),
            "Add Process (P)",
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
            "Add Link (L)",
            lambda: self.main_window.set_mode(Mode.ADD_LINK),
            checkable=True
        )
        
        # Combo pro default link type
        self.main_window.cmb_default_link_type = QComboBox()
        
        # Přidej procedurální linky
        self.main_window.cmb_default_link_type.addItem("─── Procedural ───")
        self.main_window.cmb_default_link_type.model().item(0).setEnabled(False)
        self.main_window.cmb_default_link_type.addItems([
            "consumption", "result", "effect", "agent", "instrument"
        ])
        
        # Přidej oddělovač a strukturální linky
        self.main_window.cmb_default_link_type.insertSeparator(6)  # Po 5 procedurálních + 1 nadpis
        self.main_window.cmb_default_link_type.addItem("─── Structural ───")
        self.main_window.cmb_default_link_type.model().item(7).setEnabled(False)
        self.main_window.cmb_default_link_type.addItems([
            "aggregation", "exhibition", "generalization", "instantiation"
        ])
        
        self.main_window.cmb_default_link_type.setCurrentText(self.main_window.default_link_type)
        self.main_window.cmb_default_link_type.currentTextChanged.connect(
            lambda text: setattr(self.main_window, "default_link_type", text) if "───" not in text else None
        )
        tb.addWidget(QLabel("Link type:"))
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

