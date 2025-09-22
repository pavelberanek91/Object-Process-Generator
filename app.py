from __future__ import annotations
import sys
from typing import Optional

from dotenv import load_dotenv, find_dotenv
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QPalette,
    QUndoStack, 
    QUndoCommand
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
    QUndoView,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtSvg import QSvgGenerator
from constants import *
from graphics.grid import GridScene
from graphics.nodes import ObjectItem, ProcessItem, StateItem
from graphics.link import LinkItem
from ui.view import EditorView
from ui.tabs import RenameableTabBar
from opl import parser as opl_parser
from opl import generator as opl_generator
from ai.nl2opl import nl_to_opl

from ui.icons import icon_shape, icon_std
from persistence.json_io import (
    save_scene_as_json,
    load_scene_from_json,
    safe_base_filename,
)
from undo.commands import DeleteItemsCommand, ClearAllCommand, AddStateCommand, AddNodeCommand



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OPM Editor — MVP")
        
        # Tabs jsou trvalý central widget
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        bar = RenameableTabBar(self.tabs)
        self.tabs.setTabBar(bar)
        bar.renameRequested.connect(self._rename_tab)

        # Stavové proměnné
        self.mode = Mode.SELECT
        self._scale = 1.0
        self.pending_link_src: Optional[QGraphicsItem] = None
        self.default_link_type = LINK_TYPES[0]
        self._suppress_combo = False

        # Založ první canvas (to samo nastaví self.view/self.scene přes _activate_view)
        self._new_canvas("Canvas 1")

        # Toolbary / docky až po vytvoření prvního canvase
        self.create_toolbar()
        self.create_prop_dock()
        #self.scene.selectionChanged.connect(self.sync_selected_to_props)

    # Pomocník – tlač příkazy na undo stack
    def push_cmd(self, cmd):
        self.undo_stack.push(cmd)

    # --------- UI ----------
    def create_toolbar(self):
        tb = QToolBar("Tools")
        self.addToolBar(Qt.TopToolBarArea, tb)

        def add_btn(title, slot, checkable=False, group=None):
            act = QAction(title, self)
            act.triggered.connect(slot)
            tb.addAction(act)
            act.setCheckable(checkable)
            if group: group.addAction(act)
            return act

        def add_icon_btn(icon, tooltip, slot, checkable=False, group=None):
            act = QAction(icon, "", self)
            act.setToolTip(tooltip)
            act.setStatusTip(tooltip)
            act.triggered.connect(slot)
            act.setCheckable(checkable)
            tb.addAction(act)
            if group: group.addAction(act)
            return act

        def add_spacing(tb: QToolBar, width: int = 16):
            spacer = QWidget()
            spacer.setFixedWidth(width)
            spacer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            tb.addWidget(spacer)
            return spacer

        file_menu = QMenu("File", self)
        file_menu.addAction("New OPD", lambda: self._new_canvas())
        file_menu.addSeparator()
        file_menu.addAction("Export OPD",  lambda: save_scene_as_json(self.scene, self._current_tab_title()))
        file_menu.addAction("Import OPD (Current Tab)", lambda: load_scene_from_json(
                            self.scene, self.allowed_link, new_canvas_callback=self._new_canvas, 
                            new_tab=False))
        file_menu.addAction("Import OPD (New Tab)", lambda: load_scene_from_json(
                            self.scene, self.allowed_link, new_canvas_callback=self._new_canvas, 
                            new_tab=True))
        file_menu.addSeparator()
        file_menu.addAction("Rename OPD", lambda: self._rename_tab(self.tabs.currentIndex()))
        file_menu.addAction("Close Tab", lambda: self._close_current_tab())
        file_menu.addSeparator()
        file_menu.addAction("Exit", QApplication.instance().quit)
        # act_exit = QAction("Exit", self)
        # act_exit.setShortcut(QKeySequence.Quit)   # Ctrl+Q na Win/Linux, ⌘Q na macOS TODO: nefunguje
        # act_exit.triggered.connect(QApplication.instance().quit)
        # file_menu.addAction(act_exit)
        file_btn = QToolButton()
        file_btn.setText("File")
        file_btn.setMenu(file_menu)
        file_btn.setPopupMode(QToolButton.InstantPopup)
        file_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tb.addWidget(file_btn)

        tb.addSeparator()
        add_btn("Create OPL", self.import_opl_dialog)
        tb.addSeparator()
        add_btn("Generate OPL", self.open_nl_to_opl_dialog)
        
        
        tb.addSeparator()
        export_menu = QMenu("Image", self)
        export_menu.addAction("Save as JPG",  lambda: self.export_image("jpg"))
        export_menu.addAction("Save as PNG",  lambda: self.export_image("png"))
        export_menu.addAction("Save as SVG",  lambda: self.export_image("svg"))
        export_btn = QToolButton()
        export_btn.setText("Image")
        export_btn.setMenu(export_menu)
        export_btn.setPopupMode(QToolButton.InstantPopup)
        export_btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tb.addWidget(export_btn)

        add_spacing(tb, 16)

        act_select = QAction(icon_shape("cursor"), "", self)
        act_select.setToolTip("Select/Move")
        act_select.setCheckable(True)
        tb.addAction(act_select)
        act_select.triggered.connect(lambda: self.set_mode(Mode.SELECT))

        tb.addSeparator()
        act_obj  = add_icon_btn(icon_shape("object"), "Add Object",  lambda: self.set_mode(Mode.ADD_OBJECT),  True)
        tb.addSeparator()
        act_proc = add_icon_btn(icon_shape("process"), "Add Process", lambda: self.set_mode(Mode.ADD_PROCESS), True)
        tb.addSeparator()
        act_state = add_icon_btn(icon_shape("state"), "Add State",    lambda: self.set_mode(Mode.ADD_STATE),   True)
        tb.addSeparator()
        act_link = add_icon_btn(icon_shape("link"),  "Add Link",     lambda: self.set_mode(Mode.ADD_LINK),    True)

        group = QActionGroup(self)
        group.setExclusive(True)
        for a in (act_select, act_obj, act_proc, act_state, act_link):
            group.addAction(a)
        act_select.setChecked(True)
        self.actions = {
            Mode.SELECT:act_select,
            Mode.ADD_OBJECT:act_obj,
            Mode.ADD_PROCESS:act_proc,
            Mode.ADD_STATE:act_state,
            Mode.ADD_LINK:act_link
        }

        # Ostatní (necheckable)
        tb.addSeparator()
        add_icon_btn(icon_shape("delete"), "Delete (Del)", self.delete_selected)
        tb.addSeparator()
        add_icon_btn(icon_std(self, QStyle.SP_DialogDiscardButton), "Clear All", self.clear_all)
        tb.addSeparator()
        add_icon_btn(icon_shape("zoom_in"),  "Zoom In (Ctrl + Wheel)",  self.zoom_in)
        tb.addSeparator()
        add_icon_btn(icon_shape("zoom_out"), "Zoom Out (Ctrl + Wheel)", self.zoom_out)
        tb.addSeparator()
        add_icon_btn(icon_shape("reset_zoom"), "Reset Zoom", self.zoom_reset)

        # undo/redo prikazy
        self.undo_stack = QUndoStack(self)
        tb = self.addToolBar("Edit")
        act_undo = self.undo_stack.createUndoAction(self, "Undo")
        act_redo = self.undo_stack.createRedoAction(self, "Redo")
        tb.addAction(act_undo); tb.addAction(act_redo)
        act_undo.setShortcut("Ctrl+Z")
        act_redo.setShortcut("Ctrl+Y")

    def _new_canvas(self, title: str | None = None):
        scene = GridScene(self)
        scene.setSceneRect(-5000, -5000, 10000, 10000)

        view = EditorView(scene, self)  # EditorView už zná self jako "app"
        # QGraphicsView je QWidget → můžeme ho dát přímo do tabu
        idx = self.tabs.addTab(view, title or f"Canvas {self.tabs.count() + 1}")
        self.tabs.setCurrentIndex(idx)

        # Přesměruj interní ukazatele a signály na aktuální scene/view
        self._activate_view(view)
        
        return view

    def _activate_view(self, view):
        # odpoj starý selectionChanged, pokud nějaký byl
        try:
            self.scene.selectionChanged.disconnect(self.sync_selected_to_props)
        except Exception:
            pass
        self.view = view
        self.scene = view.scene()
        self.scene.selectionChanged.connect(self.sync_selected_to_props)

        # volitelně: vyčisti overlaye/stav linku
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
        if idx < 0:
            return
        view = self.tabs.widget(idx)   # je to přímo EditorView
        self._activate_view(view)

    def _close_current_tab(self):
        idx = self.tabs.currentIndex()
        if idx >= 0:
            self.tabs.removeTab(idx)
        # když nic nezbyde, můžeš automaticky založit prázdný canvas:
        if self.tabs.count() == 0:
            self._new_canvas("Canvas 1")

    def _rename_tab(self, idx: int):
        # bezpečnostní kontrola
        if idx < 0 or idx >= self.tabs.count():
            return
        current = self.tabs.tabText(idx)
        text, ok = QInputDialog.getText(self, "Rename OPD", "New name:", text=current)
        if ok:
            new = text.strip()
            if new:
                self.tabs.setTabText(idx, new)

    def create_prop_dock(self):
        dock = QDockWidget("Properties", self); panel = QWidget(); form = QFormLayout(panel)
        self.ed_label = QLineEdit(); self.ed_label.setPlaceholderText("Label…")
        self.ed_label.editingFinished.connect(self.apply_label_change)
        form.addRow("Label", self.ed_label)

        self.cmb_link_type = QComboBox(); self.cmb_link_type.addItems(LINK_TYPES)
        self.cmb_link_type.setCurrentText(self.default_link_type)
        self.cmb_link_type.currentTextChanged.connect(self.handle_link_type_combo_change)
        self.lbl_link_type = QLabel("Link type (for new links)")
        form.addRow(self.lbl_link_type, self.cmb_link_type)

        self.btn_generate_opl = QPushButton("Generate OPL (preview)")
        self.btn_generate_opl.clicked.connect(self.preview_opl)
        form.addRow(self.btn_generate_opl)

        panel.setLayout(form); dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    # --------- Modes & zoom ----------
    

    def set_mode(self, mode: str):
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

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
            event.accept()
            return
        if event.key() == Qt.Key_Escape and self.mode == Mode.ADD_LINK and self.pending_link_src is not None:
            self.cancel_link_creation()
            event.accept()
            return
        super().keyPressEvent(event)

    def zoom_in(self):
        self._scale = min(self._scale * 1.2, 5.0)
        self.view.scale(1.2, 1.2)

    def zoom_out(self):
        self._scale = max(self._scale / 1.2, 0.2)
        self.view.scale(1/1.2, 1/1.2)

    def zoom_reset(self):
        self._scale = 1.0
        self.view.resetTransform()

    def snap(self, p: QPointF) -> QPointF:
        return QPointF(round(p.x()/GRID_SIZE)*GRID_SIZE, round(p.y()/GRID_SIZE)*GRID_SIZE)

    # --------- Node ops ----------
    def add_object(self, pos: QPointF):
        item = ObjectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H))
        item.setPos(self.snap(pos))
        cmd = AddNodeCommand(self.scene, item, "Add Object")
        self.push_cmd(cmd)

    def add_process(self, pos: QPointF):
        item = ProcessItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H))
        item.setPos(self.snap(pos))
        cmd = AddNodeCommand(self.scene, item, "Add Process")
        self.push_cmd(cmd)

    def add_state(self, obj: ObjectItem, pos_in_scene: QPointF):
        p = obj.mapFromScene(self.snap(pos_in_scene))
        r = obj.rect()
        x = min(max(p.x()-STATE_W/2, r.left()+6), r.right()-STATE_W-6)
        y = min(max(p.y()-STATE_H/2, r.top()+6),  r.bottom()-STATE_H-6)
        rect = QRectF(x, y, STATE_W, STATE_H)
        self.push_cmd(AddStateCommand(self.scene, obj, rect, "State"))


    def allowed_link(self, src_item: QGraphicsItem, dst_item: QGraphicsItem, link_type: str) -> tuple[bool, str]:
        lt = (link_type or "").lower()
        s_kind = getattr(src_item, "kind", None)
        d_kind = getattr(dst_item, "kind", None)

        # Treat state as object
        if s_kind == "state":
            s_kind = "object"
        if d_kind == "state":
            d_kind = "object"

        if lt in PROCEDURAL_TYPES:
            if s_kind == "object" and d_kind == "process" and lt in {"input","consumption","agent","instrument","effect"}:
                return True, ""
            if s_kind == "process" and d_kind == "object" and lt in {"output","result","effect"}:
                return True, ""
            return False, ("Procedurální vazba musí spojovat Object/State ↔ Process. "
                        "Object/State → Process [input|consumption|agent|instrument|effect]; "
                        "Process → Object/State [output|result|effect].")

        if lt in STRUCTURAL_TYPES:
            if s_kind in {"object","process"} and s_kind == d_kind:
                return True, ""
            return False, "Strukturální vazba musí být Object/State↔Object/State nebo Process↔Process (ne křížem)."

        return True, ""

    def handle_link_click(self, pos: QPointF):
        item = self.scene.itemAt(pos, self.view.transform())
        if not isinstance(item, (ObjectItem, ProcessItem, StateItem)):
            return
        
        if self.pending_link_src is None:
            self.pending_link_src = item; 
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

    def delete_selected(self):
        items = self.scene.selectedItems()
        if not items:
            return
        self.push_cmd(DeleteItemsCommand(self.scene, items))

    def clear_all(self):
        if not self.scene.items():
            return
        self.push_cmd(ClearAllCommand(self.scene))

    # --------- Properties ----------
    def selected_item(self) -> Optional[QGraphicsItem]:
        sel = self.scene.selectedItems(); return sel[0] if sel else None

    def sync_selected_to_props(self):
        sel = self.scene.selectedItems(); it = sel[0] if sel else None
        if isinstance(it, (ObjectItem, ProcessItem, StateItem)): self.ed_label.setText(it.label)
        elif isinstance(it, LinkItem): self.ed_label.setText(it.label)
        else: self.ed_label.clear()
        links = [x for x in sel if isinstance(x, LinkItem)]
        self._suppress_combo = True
        if links:
            self.cmb_link_type.setCurrentText(links[0].link_type)
            self.lbl_link_type.setText("Link type (selected links)")
        else:
            self.cmb_link_type.setCurrentText(self.default_link_type)
            self.lbl_link_type.setText("Link type (for new links)")
        self._suppress_combo = False

    def apply_label_change(self):
        it = self.selected_item(); text = self.ed_label.text()
        if isinstance(it, (ObjectItem, ProcessItem, StateItem)): it.set_label(text)
        elif isinstance(it, LinkItem): it.set_label_text(text)

    def handle_link_type_combo_change(self, text: str):
        if getattr(self, "_suppress_combo", False): return
        links = [it for it in self.scene.selectedItems() if isinstance(it, LinkItem)]
        if not links: self.default_link_type = text; return
        invalid = []
        for ln in links:
            ok, msg = self.allowed_link(ln.src, ln.dst, text)
            if not ok: invalid.append(msg)
        if invalid:
            self._suppress_combo = True; self.cmb_link_type.setCurrentText(links[0].link_type); self._suppress_combo = False
            QMessageBox.warning(self, "Neplatný typ vazby", invalid[0]); return
        for ln in links: ln.set_link_type(text)

    # --------- OPL import/generator ----------
    def import_opl_dialog(self):
        dlg = QDialog(self); dlg.setWindowTitle("Import OPL")
        txt = QTextEdit(dlg); txt.setPlaceholderText("Vlož OPL věty, každou na samostatný řádek.")
        ok = QPushButton("Importovat", dlg); cancel = QPushButton("Zrušit", dlg)
        ok.clicked.connect(dlg.accept); cancel.clicked.connect(dlg.reject)
        v = QVBoxLayout(); v.addWidget(txt)
        h = QHBoxLayout(); h.addStretch(1); h.addWidget(ok); h.addWidget(cancel); v.addLayout(h)
        dlg.setLayout(v); dlg.resize(640, 420)
        if dlg.exec() == QDialog.Accepted:
            ignored = opl_parser.build_from_opl(self, txt.toPlainText())
            if ignored:
                QMessageBox.information(self, "Import OPL",
                    "Některé řádky nebyly rozpoznány a byly přeskočeny:\n\n• " + "\n• ".join(ignored))

    def open_nl_to_opl_dialog(self):
        dlg = QDialog(self); dlg.setWindowTitle("NL → OPL")
        inp = QTextEdit(dlg); inp.setPlaceholderText("Popiš proces/vztahy v přirozeném jazyce (CZ/EN).")
        out = QTextEdit(dlg); out.setPlaceholderText("Sem se vygeneruje OPL. Můžeš ho upravit."); out.setReadOnly(False)
        gen = QPushButton("Vygenerovat OPL", dlg)
        imp = QPushButton("Importovat do diagramu", dlg)
        cancel = QPushButton("Zrušit", dlg)

        def do_generate():
            nl = inp.toPlainText().strip()
            if not nl: QMessageBox.information(self, "NL → OPL", "Zadej text."); return
            try: opl = nl_to_opl(nl)
            except Exception as e:
                QMessageBox.warning(self, "NL → OPL", f"Generování selhalo:\n{e}"); return
            out.setPlainText(opl)

        def do_import():
            opl = out.toPlainText().strip()
            if not opl: QMessageBox.information(self, "NL → OPL", "Není co importovat."); return
            ignored = opl_parser.build_from_opl(self, opl)
            if ignored:
                QMessageBox.information(self, "Import OPL",
                    "Některé řádky nebyly rozpoznány a byly přeskočeny:\n\n• " + "\n• ".join(ignored))
            dlg.accept()

        gen.clicked.connect(do_generate); imp.clicked.connect(do_import); cancel.clicked.connect(dlg.reject)
        lay = QVBoxLayout(); lay.addWidget(QLabel("Natural Language input")); lay.addWidget(inp)
        lay.addWidget(QLabel("Generated OPL (editable)")); lay.addWidget(out)
        row = QHBoxLayout(); row.addStretch(1); row.addWidget(gen); row.addWidget(imp); row.addWidget(cancel)
        lay.addLayout(row); dlg.setLayout(lay); dlg.resize(720, 520); dlg.exec()

    def preview_opl(self):
        text = opl_generator.preview_opl(self.scene)
        dlg = QDialog(self); dlg.setWindowTitle("OPL Preview")
        txt = QTextEdit(dlg); txt.setReadOnly(True); txt.setPlainText(text)
        btn_close = QPushButton("Close", dlg); btn_save = QPushButton("Save…", dlg)
        def do_save():
            path, _ = QFileDialog.getSaveFileName(self, "Save OPL", "opl.txt", "Text (*.txt)")
            if path:
                with open(path, "w", encoding="utf-8") as f: f.write(txt.toPlainText())
        btn_save.clicked.connect(do_save); btn_close.clicked.connect(dlg.accept)
        layout = QVBoxLayout(); layout.addWidget(txt)
        row = QHBoxLayout(); row.addStretch(1); row.addWidget(btn_save); row.addWidget(btn_close)
        layout.addLayout(row); dlg.setLayout(layout); dlg.resize(600, 400); dlg.exec()


    def export_image(self, kind: str="png"):
        base = safe_base_filename()

        if kind in "jpg":
            path, _ = QFileDialog.getSaveFileName(self, "Export JPG", f"{base}.jpg", "JPEG (*.jpg *.jpeg)")
            if not path:
                return
            rb = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
            img = QImage(int(rb.width()), int(rb.height()), QImage.Format_RGB32)
            img.fill(Qt.white)  # 100% bílé pozadí
            painter = QPainter(img)
            self.scene.render(painter, target=QRectF(0, 0, rb.width(), rb.height()), source=rb)
            painter.end()
            img.save(path, "JPG", 95)

        elif kind == "png":
            path, _ = QFileDialog.getSaveFileName(self, "Export PNG", f"{base}.png", "PNG (*.png)")
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
            path, _ = QFileDialog.getSaveFileName(self, "Export SVG", f"{base}.svg", "SVG (*.svg)")
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

    def cancel_link_creation(self):
        """Při tvorbě spojení mezi objekty se klávesou ESC předběžně ukončí"""
        self.pending_link_src = None
        # zruš náhledovou čáru
        if hasattr(self, "view") and hasattr(self.view, "clear_temp_link"):
            self.view.clear_temp_link()
        # vyčisti stavový řádek
        sb = getattr(self, "statusBar", None)
        if callable(sb):
            self.statusBar().clearMessage()
        # self.set_mode(Mode.SELECT) - pokud bychom chtěli přejít do select režimu


def make_light_palette() -> QPalette:
    palette = QPalette()

    # --- základní pozadí ---
    palette.setColor(QPalette.Window, QColor("white"))
    palette.setColor(QPalette.Base, QColor("white"))

    # --- texty ---
    palette.setColor(QPalette.WindowText, QColor("black"))  # text v labelech, titulcích
    palette.setColor(QPalette.Text, QColor("black"))        # text v editorech
    palette.setColor(QPalette.ButtonText, QColor("black"))  # text na tlačítkách
    palette.setColor(QPalette.ToolTipText, QColor("black"))

    # --- tlačítka ---
    palette.setColor(QPalette.Button, QColor("#f0f0f0"))    # světle šedé tlačítko
    palette.setColor(QPalette.Highlight, QColor("#0078d7")) # modrý highlight (Windows-like)
    palette.setColor(QPalette.HighlightedText, QColor("white"))

    # --- disabled stavy ---
    disabled_text = QColor(120, 120, 120)
    palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)

    return palette


def main():
    load_dotenv(find_dotenv(), override=True)
    app = QApplication(sys.argv)

    # Nastavíme světlý vzhled
    app.setPalette(make_light_palette())

    app.setStyleSheet("""
        QToolBar {
            background: white;
            border: none;   /* volitelné – skryje defaultní čáru */
        }
        QToolBar QToolButton {
            background: white;
            color: black;
            border: 1px solid #dcdcdc;
            border-radius: 6px;
            padding: 4px 6px;
        }
        QToolBar QToolButton:hover {
            background: #f5f5f5;
        }
        QToolBar QToolButton:pressed {
            background: #eaeaea;
        }
        QToolBar QToolButton:checked {
            background: #e6f0ff;
            border-color: #699BFF;
        }
        QToolBar QToolButton:disabled {
            color: #888;
        }
    """)
    
    w = MainWindow(); w.resize(1100, 700); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()