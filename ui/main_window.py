"""Hlavní okno aplikace OPM Editor."""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QImage,
    QPainter,
    QUndoStack,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsItem,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)
from PySide6.QtSvg import QSvgGenerator

from constants import *
from graphics.grid import GridScene
from graphics.nodes import ObjectItem, ProcessItem, StateItem
from graphics.link import LinkItem
from ui.view import EditorView
from ui.tabs import RenameableTabBar
from ui.toolbar import ToolbarManager
from ui.properties_panel import PropertiesPanel
from ui.dialogs import show_opl_import_dialog, show_nl_to_opl_dialog, show_opl_preview_dialog
from persistence.json_io import safe_base_filename
from undo.commands import DeleteItemsCommand, ClearAllCommand, AddStateCommand, AddNodeCommand


class MainWindow(QMainWindow):
    """Hlavní okno aplikace OPM Editor."""
    
    _instance = None
    
    @classmethod
    def instance(cls):
        """Vrátí instanci MainWindow (singleton pattern)."""
        return cls._instance
    
    def __init__(self):
        super().__init__()
        MainWindow._instance = self
        self.setWindowTitle("OPM Editor — MVP")
        
        # Inicializace stavových proměnných
        self.mode = Mode.SELECT
        self._scale = 1.0
        self.pending_link_src: Optional[QGraphicsItem] = None
        self.default_link_type = LINK_TYPES[0]
        self._suppress_combo = False
        
        # Undo stack
        self.undo_stack = QUndoStack(self)
        
        # Inicializace UI
        self._init_tabs()
        self._init_first_canvas()
        self._init_toolbars()
        self._init_properties_panel()
    
    def _init_tabs(self):
        """Inicializuje tab widget."""
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        
        bar = RenameableTabBar(self.tabs)
        self.tabs.setTabBar(bar)
        bar.renameRequested.connect(self._rename_tab)
    
    def _init_first_canvas(self):
        """Vytvoří první canvas."""
        self._new_canvas("Canvas 1")
    
    def _init_toolbars(self):
        """Inicializuje toolbary."""
        toolbar_manager = ToolbarManager(self)
        toolbar_manager.create_all_toolbars()
    
    def _init_properties_panel(self):
        """Inicializuje properties panel."""
        self.dock_props = PropertiesPanel(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_props)
        
        # Připojí změnu výběru na panel
        self.scene.selectionChanged.connect(self.update_properties_panel)
        self.update_properties_panel()
    
    # ========== Pomocné metody ==========
    
    def push_cmd(self, cmd):
        """Přidá příkaz na undo stack."""
        self.undo_stack.push(cmd)
    
    def snap(self, p: QPointF) -> QPointF:
        """Přichytí bod na mřížku."""
        return QPointF(
            round(p.x() / GRID_SIZE) * GRID_SIZE,
            round(p.y() / GRID_SIZE) * GRID_SIZE
        )
    
    def selected_item(self) -> Optional[QGraphicsItem]:
        """Vrátí první vybraný prvek nebo None."""
        sel = self.scene.selectedItems()
        return sel[0] if sel else None
    
    # ========== Tab management ==========
    
    def _new_canvas(self, title: str | None = None):
        """Vytvoří nový canvas v novém tabu."""
        scene = GridScene(self)
        scene.setSceneRect(-5000, -5000, 10000, 10000)

        view = EditorView(scene, self)
        idx = self.tabs.addTab(view, title or f"Canvas {self.tabs.count() + 1}")
        self.tabs.setCurrentIndex(idx)

        self._activate_view(view)
        return view

    def _activate_view(self, view):
        """Aktivuje daný view a připojí signály."""
        # Odpojí starý selectionChanged
        try:
            self.scene.selectionChanged.disconnect(self.sync_selected_to_props)
        except Exception:
            pass
        
        self.view = view
        self.scene = view.scene()
        self.scene.selectionChanged.connect(self.sync_selected_to_props)

        # Vyčistí overlaye/stav linku
        self.view.clear_overlays()
        self.pending_link_src = None

    def _current_tab_title(self) -> str:
        """Vrátí text aktivní záložky nebo fallback."""
        idx = self.tabs.currentIndex() if hasattr(self, "tabs") else -1
        if idx >= 0:
            t = self.tabs.tabText(idx).strip()
            return t if t else "Canvas"
        return "Canvas"

    def _on_tab_changed(self, idx: int):
        """Handler pro změnu tabu."""
        if idx < 0:
            return
        view = self.tabs.widget(idx)
        self._activate_view(view)

    def _close_current_tab(self):
        """Zavře aktuální tab."""
        idx = self.tabs.currentIndex()
        if idx >= 0:
            self.tabs.removeTab(idx)
        
        # Když nic nezbyde, založí prázdný canvas
        if self.tabs.count() == 0:
            self._new_canvas("Canvas 1")

    def _rename_tab(self, idx: int):
        """Přejmenuje tab."""
        if idx < 0 or idx >= self.tabs.count():
            return
        
        current = self.tabs.tabText(idx)
        text, ok = QInputDialog.getText(self, "Rename OPD", "New name:", text=current)
        if ok:
            new = text.strip()
            if new:
                self.tabs.setTabText(idx, new)
    
    # ========== Mode & zoom ==========
    
    def set_mode(self, mode: str):
        """Nastaví režim editoru."""
        self.mode = mode
        try:
            self.actions[mode].setChecked(True)
        except Exception:
            pass
        
        if mode == Mode.SELECT:
            self.view.setCursor(Qt.ArrowCursor)
            self.view.setDragMode(EditorView.RubberBandDrag)
            self.view.clear_overlays()
        else:
            self.view.setCursor(Qt.CrossCursor)
            self.view.setDragMode(EditorView.NoDrag)
        
        self.statusBar().showMessage(f"Mode: {mode}")
        
        if mode != Mode.ADD_LINK:
            self.pending_link_src = None
            self.view.clear_temp_link()

    def zoom_in(self):
        """Přiblíží view."""
        self._scale = min(self._scale * 1.2, 5.0)
        self.view.scale(1.2, 1.2)

    def zoom_out(self):
        """Oddálí view."""
        self._scale = max(self._scale / 1.2, 0.2)
        self.view.scale(1/1.2, 1/1.2)

    def zoom_reset(self):
        """Resetuje zoom."""
        self._scale = 1.0
        self.view.resetTransform()
    
    # ========== Node operations ==========
    
    def add_object(self, pos: QPointF):
        """Přidá nový objekt."""
        item = ObjectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H))
        item.setPos(self.snap(pos))
        cmd = AddNodeCommand(self.scene, item, "Add Object")
        self.push_cmd(cmd)

    def add_process(self, pos: QPointF):
        """Přidá nový proces."""
        item = ProcessItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H))
        item.setPos(self.snap(pos))
        cmd = AddNodeCommand(self.scene, item, "Add Process")
        self.push_cmd(cmd)

    def add_state(self, obj: ObjectItem, pos_in_scene: QPointF):
        """Přidá nový stav do objektu."""
        p = obj.mapFromScene(self.snap(pos_in_scene))
        r = obj.rect()
        x = min(max(p.x()-STATE_W/2, r.left()+6), r.right()-STATE_W-6)
        y = min(max(p.y()-STATE_H/2, r.top()+6), r.bottom()-STATE_H-6)
        rect = QRectF(x, y, STATE_W, STATE_H)
        self.push_cmd(AddStateCommand(self.scene, obj, rect, "State"))
    
    # ========== Link operations ==========
    
    def allowed_link(self, src_item: QGraphicsItem, dst_item: QGraphicsItem, link_type: str) -> tuple[bool, str]:
        """Kontroluje, zda je link povolen."""
        # TODO: validace zatím vypnutá kvůli AI generování
        return True, ""

    def handle_link_click(self, pos: QPointF):
        """Zpracuje kliknutí v režimu přidávání linku."""
        item = self.scene.itemAt(pos, self.view.transform())
        if not isinstance(item, (ObjectItem, ProcessItem, StateItem)):
            return
        
        if self.pending_link_src is None:
            self.pending_link_src = item
            self.statusBar().showMessage("Choose target node…")
        else:
            if item is self.pending_link_src:
                self.pending_link_src = None
                return
            
            ok, msg = self.allowed_link(self.pending_link_src, item, self.default_link_type)
            if not ok:
                QMessageBox.warning(self, "Neplatná vazba", msg)
                self.pending_link_src = None
                return

            self.scene.addItem(LinkItem(self.pending_link_src, item, self.default_link_type))
            self.pending_link_src = None
            self.statusBar().clearMessage()

    def cancel_link_creation(self):
        """Zruší tvorbu linku."""
        self.pending_link_src = None
        
        if hasattr(self, "view") and hasattr(self.view, "clear_temp_link"):
            self.view.clear_temp_link()
        
        sb = getattr(self, "statusBar", None)
        if callable(sb):
            self.statusBar().clearMessage()
    
    # ========== Delete operations ==========
    
    def delete_selected(self):
        """Smaže vybrané prvky."""
        items = self.scene.selectedItems()
        if not items:
            return
        self.push_cmd(DeleteItemsCommand(self.scene, items))

    def clear_all(self):
        """Smaže všechny prvky ze scény."""
        if not self.scene.items():
            return
        self.push_cmd(ClearAllCommand(self.scene))
    
    # ========== Properties panel ==========
    
    def update_properties_panel(self):
        """Aktualizuje properties panel."""
        if hasattr(self, 'dock_props'):
            self.dock_props.update_for_selection()
    
    def sync_selected_to_props(self):
        """Synchronizuje výběr do properties panelu."""
        if hasattr(self, 'dock_props'):
            self.dock_props.sync_selection_to_props()
    
    # ========== Dialogy ==========
    
    def import_opl_dialog(self):
        """Zobrazí dialog pro import OPL."""
        show_opl_import_dialog(self)

    def open_nl_to_opl_dialog(self):
        """Zobrazí dialog pro NL → OPL."""
        show_nl_to_opl_dialog(self)

    def preview_opl(self):
        """Zobrazí náhled generovaného OPL."""
        show_opl_preview_dialog(self.scene, self)
    
    # ========== Export ==========
    
    def export_image(self, kind: str = "png"):
        """Exportuje scénu jako obrázek."""
        base = safe_base_filename()

        if kind in "jpg":
            path, _ = QFileDialog.getSaveFileName(
                self, "Export JPG", f"{base}.jpg", "JPEG (*.jpg *.jpeg)"
            )
            if not path:
                return
            rb = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
            img = QImage(int(rb.width()), int(rb.height()), QImage.Format_RGB32)
            img.fill(Qt.white)
            painter = QPainter(img)
            self.scene.render(painter, target=QRectF(0, 0, rb.width(), rb.height()), source=rb)
            painter.end()
            img.save(path, "JPG", 95)

        elif kind == "png":
            path, _ = QFileDialog.getSaveFileName(
                self, "Export PNG", f"{base}.png", "PNG (*.png)"
            )
            if not path:
                return
            rb = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
            img = QImage(int(rb.width()), int(rb.height()), QImage.Format_ARGB32_Premultiplied)
            img.fill(0x00FFFFFF)
            painter = QPainter(img)
            self.scene.render(painter, target=QRectF(0, 0, rb.width(), rb.height()), source=rb)
            painter.end()
            img.save(path)

        elif kind == "svg":
            path, _ = QFileDialog.getSaveFileName(
                self, "Export SVG", f"{base}.svg", "SVG (*.svg)"
            )
            if not path:
                return
            rb = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
            gen = QSvgGenerator()
            gen.setFileName(path)
            gen.setSize(rb.size().toSize())
            gen.setViewBox(rb)
            painter = QPainter(gen)
            self.scene.render(painter, target=rb, source=rb)
            painter.end()

        else:
            QMessageBox.warning(self, "Export", f"Unsupported format: {kind}")
    
    # ========== Keyboard events ==========
    
    def keyPressEvent(self, event):
        """Zpracuje stisknutí klávesy."""
        # Mazání
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
            event.accept()
            return
        
        # Zrušení linku
        if (event.key() == Qt.Key_Escape 
                and self.mode == Mode.ADD_LINK 
                and self.pending_link_src is not None):
            self.cancel_link_creation()
            event.accept()
            return
        
        # Rychlé přepínání typu linku čísly
        if event.key() in (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4, 
                          Qt.Key_5, Qt.Key_6, Qt.Key_7):
            mapping = {
                Qt.Key_1: "input",
                Qt.Key_2: "output",
                Qt.Key_3: "consumption",
                Qt.Key_4: "result",
                Qt.Key_5: "effect",
                Qt.Key_6: "agent",
                Qt.Key_7: "instrument",
            }
            lt = mapping.get(event.key())
            sel = [it for it in self.scene.selectedItems() if isinstance(it, LinkItem)]
            
            if sel:
                for ln in sel:
                    ln.set_link_type(lt)
                self.update_properties_panel()
            else:
                # Když není nic vybráno, nastaví se default pro další link
                self.default_link_type = lt
                self.cmb_default_link_type.setCurrentText(lt)

            event.accept()
            return
        
        super().keyPressEvent(event)

