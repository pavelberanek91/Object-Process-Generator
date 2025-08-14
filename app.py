from __future__ import annotations
import json, sys
import os, re
import math
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Tuple

from dotenv import load_dotenv, find_dotenv
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap
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
    QStyle,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QToolButton,
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

@dataclass
class DiagramNode:
    id: str; kind: str; label: str; x: float; y: float; w: float; h: float
    parent_id: Optional[str] = None

@dataclass
class DiagramLink:
    id: str; src: str; dst: str; link_type: str; label: str = ""
    type_dx: float = 6.0; type_dy: float = -6.0; label_dx: float = 6.0; label_dy: float = 12.0

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
            act.setToolTip(tooltip); act.setStatusTip(tooltip)
            act.triggered.connect(slot); act.setCheckable(checkable)
            tb.addAction(act)
            if group: group.addAction(act)
            return act

        file_menu = QMenu("File", self)
        file_menu.addAction("New OPD", lambda: self._new_canvas())
        file_menu.addSeparator()
        file_menu.addAction("Export OPD",  lambda: self.save_json())
        file_menu.addAction("Import OPD (Current Tab)", self.load_json_into_current)
        file_menu.addAction("Import OPD (New Tab)", self.load_json_into_new_canvas)
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

        # tb.addSeparator()
        # act_select = QAction("Select/Move", self)
        # act_select.setCheckable(True)
        # tb.addAction(act_select)
        # act_select.triggered.connect(lambda: self.set_mode(Mode.SELECT))
        # tb.addSeparator()
        # act_obj  = add_btn("Add Object",  lambda: self.set_mode(Mode.ADD_OBJECT), True)
        # tb.addSeparator()
        # act_proc = add_btn("Add Process", lambda: self.set_mode(Mode.ADD_PROCESS), True)
        # tb.addSeparator()
        # act_state= add_btn("Add State",   lambda: self.set_mode(Mode.ADD_STATE), True)
        # tb.addSeparator()
        # act_link = add_btn("Add Link",    lambda: self.set_mode(Mode.ADD_LINK), True)

        act_select = QAction(self._icon_shape("cursor"), "", self)
        act_select.setToolTip("Select/Move")
        act_select.setCheckable(True)
        tb.addAction(act_select)
        act_select.triggered.connect(lambda: self.set_mode(Mode.SELECT))

        tb.addSeparator()
        act_obj  = add_icon_btn(self._icon_shape("object"), "Add Object",  lambda: self.set_mode(Mode.ADD_OBJECT),  True)
        tb.addSeparator()
        act_proc = add_icon_btn(self._icon_shape("process"), "Add Process", lambda: self.set_mode(Mode.ADD_PROCESS), True)
        tb.addSeparator()
        act_state = add_icon_btn(self._icon_shape("state"), "Add State",    lambda: self.set_mode(Mode.ADD_STATE),   True)
        tb.addSeparator()
        act_link = add_icon_btn(self._icon_shape("link"),  "Add Link",     lambda: self.set_mode(Mode.ADD_LINK),    True)

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
        add_icon_btn(self._icon_std(QStyle.SP_TrashIcon), "Delete (Del)", self.delete_selected)
        tb.addSeparator()
        add_icon_btn(self._icon_std(QStyle.SP_DialogDiscardButton), "Clear All", self.clear_all)
        tb.addSeparator()
        add_icon_btn(self._icon_shape("zoom_in"),  "Zoom In (Ctrl + Wheel)",  self.zoom_in)
        tb.addSeparator()
        add_icon_btn(self._icon_shape("zoom_out"), "Zoom Out (Ctrl + Wheel)", self.zoom_out)
        tb.addSeparator()
        # Reset – zkusíme systémovou, případně použij _icon_std(QStyle.SP_BrowserReload)
        reset_icon = self._icon_std(QStyle.SP_DialogResetButton) or self._icon_std(QStyle.SP_BrowserReload)
        add_icon_btn(reset_icon, "Reset Zoom", self.zoom_reset)

    def _new_canvas(self, title: str | None = None):
        scene = GridScene(self)
        scene.setSceneRect(-5000, -5000, 10000, 10000)

        view = EditorView(scene, self)  # EditorView už zná self jako "app"
        # QGraphicsView je QWidget → můžeme ho dát přímo do tabu
        idx = self.tabs.addTab(view, title or f"Canvas {self.tabs.count() + 1}")
        self.tabs.setCurrentIndex(idx)

        # Přesměruj interní ukazatele a signály na aktuální scene/view
        self._activate_view(view)

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
    # Továrna na ikonky
    def _icon_shape(self, kind: str, size: int = 22) -> QIcon:
        """Vykreslí jednoduché vektorové ikonky (object/process/state/link/zoom+/zoom-)."""
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(Qt.black, 2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        if kind == "cursor":
            path = QPainterPath()
            path.moveTo(4, 3)
            path.lineTo(size - 8, size // 2)
            path.lineTo(size - 12, size // 2)
            path.lineTo(size - 4, size - 5)
            path.lineTo(size - 8, size - 3)
            path.lineTo(size - 16, size // 2 + 2)
            path.lineTo(4, 3)
            p.setBrush(Qt.black)
            p.drawPath(path)

        if kind == "object":
            r = QRectF(3, 4, size - 6, size - 8)
            p.drawRoundedRect(r, 4, 4)

        elif kind == "process":
            r = QRectF(3, 4, size - 6, size - 8)
            p.drawEllipse(r)

        elif kind == "state":
            r = QRectF(5, 7, size - 10, size - 14)
            p.drawRoundedRect(r, 4, 4)

        elif kind == "link":
            path = QPainterPath(QPointF(4, size - 6))
            path.lineTo(size - 8, 6)
            p.drawPath(path)
            # šipka
            ax, ay = size - 8, 6
            bx, by = size - 14, 12
            ang = math.atan2(ay - by, ax - bx)
            L = 7
            p.drawLine(ax, ay, ax - L * math.cos(ang + math.pi / 6), ay - L * math.sin(ang + math.pi / 6))
            p.drawLine(ax, ay, ax - L * math.cos(ang - math.pi / 6), ay - L * math.sin(ang - math.pi / 6))

        elif kind in ("zoom_in", "zoom_out"):
            # lupa
            cx, cy, r = size / 2 - 3, size / 2 - 3, size / 2 - 6
            p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
            p.drawLine(cx + r - 1, cy + r - 1, size - 3, size - 3)  # držátko
            # plus/minus
            p.drawLine(cx - r / 2 + 1, cy, cx + r / 2 - 1, cy)
            if kind == "zoom_in":
                p.drawLine(cx, cy - r / 2 + 1, cx, cy + r / 2 - 1)

        p.end()
        return QIcon(pm)

    def _icon_std(self, sp):
        """Nativní systémová ikonka (QStyle)."""
        return self.style().standardIcon(sp)

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
        item = ObjectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H)); item.setPos(self.snap(pos))
        self.scene.addItem(item)

    def add_process(self, pos: QPointF):
        item = ProcessItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H)); item.setPos(self.snap(pos))
        self.scene.addItem(item)

    def add_state(self, obj: ObjectItem, pos_in_scene: QPointF):
        p = obj.mapFromScene(self.snap(pos_in_scene)); r = obj.rect()
        x = min(max(p.x()-STATE_W/2, r.left()+6), r.right()-STATE_W-6)
        y = min(max(p.y()-STATE_H/2, r.top()+6),  r.bottom()-STATE_H-6)
        self.scene.addItem(StateItem(obj, QRectF(x, y, STATE_W, STATE_H)))

    def allowed_link(self, src_item: QGraphicsItem, dst_item: QGraphicsItem, link_type: str) -> tuple[bool, str]:
        lt = (link_type or "").lower()
        s_kind = getattr(src_item, "kind", None); d_kind = getattr(dst_item, "kind", None)
        if lt in PROCEDURAL_TYPES:
            if s_kind == "object" and d_kind == "process" and lt in {"input","consumption","agent","instrument","effect"}:
                return True, ""
            if s_kind == "process" and d_kind == "object" and lt in {"output","result","effect"}:
                return True, ""
            return False, ("Procedurální vazba musí spojovat Object↔Process. "
                           "Object→Process [input|consumption|agent|instrument|effect]; "
                           "Process→Object [output|result|effect].")
        if lt in STRUCTURAL_TYPES:
            if s_kind in {"object","process"} and s_kind == d_kind:
                return True, ""
            return False, "Strukturální vazba musí být Object↔Object nebo Process↔Process (ne křížem)."
        return True, ""

    def handle_link_click(self, pos: QPointF):
        item = self.scene.itemAt(pos, self.view.transform())
        if not isinstance(item, (ObjectItem, ProcessItem)): return
        if self.pending_link_src is None:
            self.pending_link_src = item; self.statusBar().showMessage("Choose target node…")
        else:
            if item is self.pending_link_src: self.pending_link_src = None; return
            ok, msg = self.allowed_link(self.pending_link_src, item, self.default_link_type)
            if not ok:
                QMessageBox.warning(self, "Neplatná vazba", msg); self.pending_link_src = None; return
            self.scene.addItem(LinkItem(self.pending_link_src, item, self.default_link_type))
            self.pending_link_src = None; self.statusBar().clearMessage()

    def delete_selected(self):
        for it in list(self.scene.selectedItems()):
            if isinstance(it, LinkItem):
                it.remove_refs(); self.scene.removeItem(it)
            elif isinstance(it, (ObjectItem, ProcessItem, StateItem)):
                for ln in list(getattr(it, "_links", []) or []):
                    ln.remove_refs(); self.scene.removeItem(ln)
                self.scene.removeItem(it)

    def clear_all(self):
        self.view.clear_overlays(); self.pending_link_src = None; self.scene.clear()

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

    # --------- Persistence ----------
    def _safe_base_filename(self, title: str | None = None) -> str:
        """Z názvu tabu udělá bezpečný základ pro soubor (bez přípon)."""
        base = (title or self._current_tab_title()).strip()
        # zakázané znaky a přebytečné mezery nahradíme podtržítkem
        base = re.sub(r'[\\/*?:"<>|]+', "_", base)
        base = re.sub(r"\s+", "_", base)
        return base or "Canvas"

    def to_dict(self) -> Dict[str, Any]:
        nodes: List[DiagramNode] = []; links: List[DiagramLink] = []
        for it in self.scene.items():
            if isinstance(it, (ObjectItem, ProcessItem)):
                r_scene = it.mapRectToScene(it.rect())
                nodes.append(DiagramNode(
                    id=it.node_id, kind=it.kind, label=it.label,
                    x=r_scene.center().x(), y=r_scene.center().y(),
                    w=r_scene.width(), h=r_scene.height()
                ))
                if isinstance(it, ObjectItem):
                    for ch in it.childItems():
                        if isinstance(ch, StateItem):
                            sr = ch.mapRectToScene(ch.rect())
                            nodes.append(DiagramNode(
                                id=ch.node_id, kind="state", label=ch.label,
                                x=sr.center().x(), y=sr.center().y(),
                                w=sr.width(), h=sr.height(), parent_id=it.node_id
                            ))
        for it in self.scene.items():
            if isinstance(it, LinkItem):
                links.append(DiagramLink(
                    id=next_id("link"),
                    src=getattr(it.src, "node_id", ""), dst=getattr(it.dst, "node_id", ""),
                    link_type=it.link_type, label=it.label,
                    type_dx=getattr(it, "_type_offset", QPointF(6,-6)).x(),
                    type_dy=getattr(it, "_type_offset", QPointF(6,-6)).y(),
                    label_dx=(getattr(it, "_label_offset", QPointF(6,12)).x() if getattr(it, "ti_label", None) else 6.0),
                    label_dy=(getattr(it, "_label_offset", QPointF(6,12)).y() if getattr(it, "ti_label", None) else 12.0),
                ))
        return {"nodes": [asdict(n) for n in nodes], "links": [asdict(l) for l in links],
                "meta": {"format": "opm-mvp-json", "version": 1}}

    def from_dict(self, data: Dict[str, Any]):
        self.scene.clear()
        id_to_item: Dict[str, QGraphicsItem] = {}
        for n in data.get("nodes", []):
            kind = n["kind"]; pos = QPointF(n["x"], n["y"])
            if kind == "object":
                it = ObjectItem(QRectF(-n["w"]/2, -n["h"]/2, n["w"], n["h"]), n["label"])
                it.node_id = n["id"]; it.setPos(pos); self.scene.addItem(it); id_to_item[n["id"]] = it
        for n in data.get("nodes", []):
            if n["kind"] == "process":
                it = ProcessItem(QRectF(-n["w"]/2, -n["h"]/2, n["w"], n["h"]), n["label"])
                it.node_id = n["id"]; it.setPos(QPointF(n["x"], n["y"])); self.scene.addItem(it); id_to_item[n["id"]] = it
        for n in data.get("nodes", []):
            if n["kind"] == "state" and n.get("parent_id") in id_to_item:
                parent = id_to_item[n["parent_id"]]
                local_center = parent.mapFromScene(QPointF(n["x"], n["y"]))
                rect = QRectF(local_center.x()-n["w"]/2, local_center.y()-n["h"]/2, n["w"], n["h"])
                it = StateItem(parent, rect, n["label"]); it.node_id = n["id"]; self.scene.addItem(it); id_to_item[n["id"]] = it

        invalid = 0
        for l in data.get("links", []):
            src = id_to_item.get(l["src"]); dst = id_to_item.get(l["dst"])
            if src and dst:
                lt = l.get("link_type", "input")
                ok, msg = self.allowed_link(src, dst, lt)
                if not ok: invalid += 1; continue
                li = LinkItem(src, dst, lt, l.get("label", "")); self.scene.addItem(li)
                from PySide6.QtCore import QPointF as _QPF
                li._type_offset  = _QPF(l.get("type_dx", 6.0),  l.get("type_dy", -6.0))
                li._label_offset = _QPF(l.get("label_dx", 6.0), l.get("label_dy", 12.0))
                li.update_path()
        if invalid:
            QMessageBox.warning(self, "Některé vazby přeskočeny",
                f"{invalid} neplatných vazeb bylo při načítání přeskočeno.")

    def save_json(self):
        base = self._safe_base_filename()
        path, _ = QFileDialog.getSaveFileName(self, "Save OPD (JSON)", f"{base}.json", "JSON (*.json)")
        if not path: 
            return
        with open(path, "w", encoding="utf-8") as f: 
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def load_json_into_current(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import OPD (current tab)", "", "JSON (*.json)")
        if not path: 
            return
        with open(path, "r", encoding="utf-8") as f: 
            data = json.load(f)
        self.from_dict(data)

    def load_json_into_new_canvas(self):
        """Načte JSON do NOVÉ záložky (nový canvas)."""
        path, _ = QFileDialog.getOpenFileName(self, "Import OPD (new tab)", "", "JSON (*.json)")
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # název tabu z názvu souboru
        base = os.path.splitext(os.path.basename(path))[0] or "Canvas"
        self._new_canvas(base)  # aktivuje novou scénu a přepne na ni
        self.from_dict(data)

    def export_image(self, kind: str="png"):
        base = self._safe_base_filename()

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

def main():
    load_dotenv(find_dotenv(), override=True)
    app = QApplication(sys.argv)
    w = MainWindow(); w.resize(1100, 700); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()