"""Properties panel widget pro OPM Editor."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QWidget,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
)
from constants import LINK_TYPES
from graphics.nodes import ObjectItem, ProcessItem, StateItem
from graphics.link import LinkItem


class PropertiesPanel(QDockWidget):
    """Dock widget pro zobrazení a úpravu vlastností vybraných prvků."""
    
    def __init__(self, parent=None):
        super().__init__("Properties", parent)
        self.main_window = parent
        self._init_ui()
        
    def _init_ui(self):
        """Inicializace UI panelu."""
        self.panel_props = QWidget(self)
        form = QFormLayout(self.panel_props)

        # label
        self.lbl_label = QLabel("Label", self.panel_props)
        self.ed_label = QLineEdit(self.panel_props)
        self.ed_label.setPlaceholderText("Label…")
        self.ed_label.editingFinished.connect(self._on_label_changed)
        form.addRow(self.lbl_label, self.ed_label)

        # essence (podstata)
        self.lbl_essence = QLabel("Essence", self.panel_props)
        self.cmb_essence = QComboBox(self.panel_props)
        self.cmb_essence.addItems(["physical", "informational"])
        self.cmb_essence.currentTextChanged.connect(self._on_essence_changed)
        form.addRow(self.lbl_essence, self.cmb_essence)

        # affiliation (příslušnost)
        self.lbl_affiliation = QLabel("Affiliation", self.panel_props)
        self.cmb_affiliation = QComboBox(self.panel_props)
        self.cmb_affiliation.addItems(["systemic", "environmental"])
        self.cmb_affiliation.currentTextChanged.connect(self._on_affiliation_changed)
        form.addRow(self.lbl_affiliation, self.cmb_affiliation)

        # typ linku
        self.lbl_link_type = QLabel("Link type", self.panel_props)
        self.cmb_link_type = QComboBox(self.panel_props)
        
        # Přidej procedurální linky
        self.cmb_link_type.addItem("─── Procedural ───")
        self.cmb_link_type.model().item(0).setEnabled(False)  # Zakáže výběr nadpisu
        self.cmb_link_type.addItems([
            "input", "consumption", "output", "result", "effect", "agent", "instrument"
        ])
        
        # Přidej oddělovač a strukturální linky
        self.cmb_link_type.insertSeparator(8)  # Po 7 procedurálních + 1 nadpis
        self.cmb_link_type.addItem("─── Structural ───")
        self.cmb_link_type.model().item(9).setEnabled(False)  # Zakáže výběr nadpisu
        self.cmb_link_type.addItems([
            "aggregation", "exhibition", "generalization", "instantiation"
        ])
        
        self.cmb_link_type.currentTextChanged.connect(self._on_link_type_changed)
        form.addRow(self.lbl_link_type, self.cmb_link_type)
        
        # kardinality
        self.lbl_card_src = QLabel("Cardinality (src)", self.panel_props)
        self.ed_card_src = QLineEdit()
        self.ed_card_src.setPlaceholderText("e.g. 0..*")
        self.ed_card_src.editingFinished.connect(self._on_cardinality_changed)

        self.lbl_card_dst = QLabel("Cardinality (dst)", self.panel_props)
        self.ed_card_dst = QLineEdit()
        self.ed_card_dst.setPlaceholderText("e.g. 1")
        self.ed_card_dst.editingFinished.connect(self._on_cardinality_changed)

        form.addRow(self.lbl_card_src, self.ed_card_src)
        form.addRow(self.lbl_card_dst, self.ed_card_dst)

        # OPL
        self.btn_generate_opl = QPushButton("Generate OPL (preview)", self.panel_props)
        self.btn_generate_opl.clicked.connect(self._on_generate_opl)
        form.addRow(self.btn_generate_opl)

        self.panel_props.setLayout(form)
        self.setWidget(self.panel_props)
    
    def update_for_selection(self):
        """Aktualizuje panel na základě aktuálního výběru."""
        it = self._get_selected_item()
        
        print(f"[Properties] Updating for selection: {type(it).__name__ if it else 'None'}")
        
        # defaultně schováme vše, co nemá být vidět
        self.lbl_label.hide()
        self.ed_label.hide()
        self.lbl_essence.hide()
        self.cmb_essence.hide()
        self.lbl_affiliation.hide()
        self.cmb_affiliation.hide()
        self.lbl_link_type.hide()
        self.cmb_link_type.hide()
        self.ed_card_src.hide()
        self.ed_card_dst.hide()
        self.lbl_card_src.hide()
        self.lbl_card_dst.hide()

        if isinstance(it, (ObjectItem, ProcessItem)):
            # Objekt / proces → má label + essence + affiliation
            print(f"[Properties] Showing properties for {it.label}")
            self.lbl_label.show()
            self.ed_label.show()
            self.ed_label.setEnabled(True)
            self.ed_label.setText(it.label)
            
            self.lbl_essence.show()
            self.cmb_essence.show()
            self.cmb_essence.setCurrentText(it.essence)
            
            self.lbl_affiliation.show()
            self.cmb_affiliation.show()
            self.cmb_affiliation.setCurrentText(it.affiliation)
        elif isinstance(it, StateItem):
            # Stav → má jen label
            print(f"[Properties] Showing properties for state {it.label}")
            self.lbl_label.show()
            self.ed_label.show()
            self.ed_label.setEnabled(True)
            self.ed_label.setText(it.label)
        elif isinstance(it, LinkItem):
            # Link → má label + typ + kardinalitu
            print(f"[Properties] Showing properties for link")
            self.lbl_label.show()
            self.ed_label.show()
            self.ed_label.setEnabled(True)
            self.ed_label.setText(it.label)
            
            self.lbl_link_type.show()
            self.cmb_link_type.show()
            self.cmb_link_type.setCurrentText(it.link_type)
            
            # Kardinality jen pro určité typy linků
            if it.link_type in {"aggregation", "exhibition", "generalization", "instantiation"}:
                self.lbl_card_src.show()
                self.ed_card_src.show()
                self.lbl_card_dst.show()
                self.ed_card_dst.show()
                self.ed_card_src.setText(it.card_src)
                self.ed_card_dst.setText(it.card_dst)
        else:
            print(f"[Properties] No item selected or unsupported type")
    
    def sync_selection_to_props(self):
        """Synchronizuje výběr do properties panelu."""
        if not self.main_window:
            return
            
        sel = self.main_window.scene.selectedItems()
        it = sel[0] if sel else None
        
        if isinstance(it, (ObjectItem, ProcessItem, StateItem)):
            self.ed_label.setText(it.label)
        elif isinstance(it, LinkItem):
            self.ed_label.setText(it.label)
        else:
            self.ed_label.clear()
            
        links = [x for x in sel if isinstance(x, LinkItem)]
        self.main_window._suppress_combo = True
        if links:
            self.cmb_link_type.setCurrentText(links[0].link_type)
            self.lbl_link_type.setText("Link type (selected links)")
        else:
            self.cmb_link_type.setCurrentText(self.main_window.default_link_type)
            self.lbl_link_type.setText("Link type (for new links)")
        self.main_window._suppress_combo = False
    
    def _get_selected_item(self):
        """Vrátí první vybraný prvek nebo None."""
        if not self.main_window:
            print("[Properties] No main_window!")
            return None
        if not hasattr(self.main_window, 'scene'):
            print("[Properties] main_window has no scene!")
            return None
        sel = self.main_window.scene.selectedItems()
        print(f"[Properties] Selected items count: {len(sel)}")
        return sel[0] if sel else None
    
    def _on_label_changed(self):
        """Handler pro změnu labelu."""
        if not self.main_window:
            return
            
        selected = self.main_window.scene.selectedItems()
        if not selected:
            return
        item = selected[0]

        new_text = self.ed_label.text().strip()
        if not new_text or new_text == item.label:
            return

        from undo.commands import SetLabelCommand
        cmd = SetLabelCommand(item, new_text)
        self.main_window.push_cmd(cmd)
    
    def _on_cardinality_changed(self):
        """Handler pro změnu kardinality."""
        it = self._get_selected_item()
        if isinstance(it, LinkItem):
            it.set_card_src(self.ed_card_src.text())
            it.set_card_dst(self.ed_card_dst.text())
            it.update_path()
    
    def _on_essence_changed(self, text: str):
        """Handler pro změnu essence (physical/informational)."""
        it = self._get_selected_item()
        if isinstance(it, (ObjectItem, ProcessItem)):
            it.essence = text
            it.update()
    
    def _on_affiliation_changed(self, text: str):
        """Handler pro změnu affiliation (systemic/environmental)."""
        it = self._get_selected_item()
        if isinstance(it, (ObjectItem, ProcessItem)):
            it.affiliation = text
            it.update()
    
    def _on_link_type_changed(self, text: str):
        """Handler pro změnu typu linku."""
        # Ignoruj nadpisy (obsahují "───")
        if "───" in text:
            return
            
        if not self.main_window:
            return
            
        if getattr(self.main_window, "_suppress_combo", False):
            return
            
        from PySide6.QtWidgets import QMessageBox
        
        links = [it for it in self.main_window.scene.selectedItems() if isinstance(it, LinkItem)]
        if not links:
            self.main_window.default_link_type = text
            return
            
        invalid = []
        for ln in links:
            ok, msg = self.main_window.allowed_link(ln.src, ln.dst, text)
            if not ok:
                invalid.append(msg)
                
        if invalid:
            self.main_window._suppress_combo = True
            self.cmb_link_type.setCurrentText(links[0].link_type)
            self.main_window._suppress_combo = False
            QMessageBox.warning(self, "Neplatný typ vazby", invalid[0])
            return
            
        for ln in links:
            ln.set_link_type(text)
    
    def _on_generate_opl(self):
        """Handler pro generování OPL."""
        if self.main_window:
            self.main_window.preview_opl()

