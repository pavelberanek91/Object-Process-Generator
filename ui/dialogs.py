"""Dialogy pro OPM Editor."""
from PySide6.QtWidgets import (
    QDialog,
    QTextEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFileDialog,
    QMessageBox,
)
from opl import parser as opl_parser
from ai.nl2opl import nl_to_opl


class OPLImportDialog(QDialog):
    """Dialog pro import OPL."""
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Import OPL")
        self._init_ui()
    
    def _init_ui(self):
        """Inicializace UI dialogu."""
        self.txt = QTextEdit(self)
        self.txt.setPlaceholderText("Vlož OPL věty, každou na samostatný řádek.")
        
        ok = QPushButton("Importovat", self)
        cancel = QPushButton("Zrušit", self)
        
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        
        v = QVBoxLayout()
        v.addWidget(self.txt)
        
        h = QHBoxLayout()
        h.addStretch(1)
        h.addWidget(ok)
        h.addWidget(cancel)
        v.addLayout(h)
        
        self.setLayout(v)
        self.resize(640, 420)
    
    def get_opl_text(self) -> str:
        """Vrátí text OPL z dialogu."""
        return self.txt.toPlainText()


class NLtoOPLDialog(QDialog):
    """Dialog pro generování OPL z přirozeného jazyka."""
    
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("NL → OPL")
        self._init_ui()
    
    def _init_ui(self):
        """Inicializace UI dialogu."""
        self.inp = QTextEdit(self)
        self.inp.setPlaceholderText("Popiš proces/vztahy v přirozeném jazyce (CZ/EN).")
        
        self.out = QTextEdit(self)
        self.out.setPlaceholderText("Sem se vygeneruje OPL. Můžeš ho upravit.")
        self.out.setReadOnly(False)
        
        gen = QPushButton("Vygenerovat OPL", self)
        imp = QPushButton("Importovat do diagramu", self)
        cancel = QPushButton("Zrušit", self)
        
        gen.clicked.connect(self._on_generate)
        imp.clicked.connect(self._on_import)
        cancel.clicked.connect(self.reject)
        
        lay = QVBoxLayout()
        lay.addWidget(QLabel("Natural Language input"))
        lay.addWidget(self.inp)
        lay.addWidget(QLabel("Generated OPL (editable)"))
        lay.addWidget(self.out)
        
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(gen)
        row.addWidget(imp)
        row.addWidget(cancel)
        lay.addLayout(row)
        
        self.setLayout(lay)
        self.resize(720, 520)
    
    def _on_generate(self):
        """Handler pro generování OPL."""
        nl = self.inp.toPlainText().strip()
        if not nl:
            QMessageBox.information(self, "NL → OPL", "Zadej text.")
            return
            
        try:
            opl = nl_to_opl(nl)
        except Exception as e:
            QMessageBox.warning(self, "NL → OPL", f"Generování selhalo:\n{e}")
            return
            
        self.out.setPlainText(opl)
    
    def _on_import(self):
        """Handler pro import OPL do diagramu."""
        opl = self.out.toPlainText().strip()
        if not opl:
            QMessageBox.information(self, "NL → OPL", "Není co importovat.")
            return
            
        ignored = opl_parser.build_from_opl(self.main_window, opl)
        if ignored:
            QMessageBox.information(
                self, 
                "Import OPL",
                "Některé řádky nebyly rozpoznány a byly přeskočeny:\n\n• " + "\n• ".join(ignored)
            )
        self.accept()


class OPLPreviewDialog(QDialog):
    """Dialog pro náhled generovaného OPL."""
    
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.setWindowTitle("OPL Preview")
        self._init_ui()
    
    def _init_ui(self):
        """Inicializace UI dialogu."""
        from opl import generator as opl_generator
        
        text = opl_generator.preview_opl(self.scene)
        
        self.txt = QTextEdit(self)
        self.txt.setReadOnly(True)
        self.txt.setPlainText(text)
        
        btn_close = QPushButton("Close", self)
        btn_save = QPushButton("Save…", self)
        
        btn_save.clicked.connect(self._on_save)
        btn_close.clicked.connect(self.accept)
        
        layout = QVBoxLayout()
        layout.addWidget(self.txt)
        
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn_save)
        row.addWidget(btn_close)
        layout.addLayout(row)
        
        self.setLayout(layout)
        self.resize(600, 400)
    
    def _on_save(self):
        """Handler pro uložení OPL do souboru."""
        path, _ = QFileDialog.getSaveFileName(self, "Save OPL", "opl.txt", "Text (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.txt.toPlainText())


def show_opl_import_dialog(main_window):
    """Zobrazí dialog pro import OPL a provede import."""
    dlg = OPLImportDialog(main_window, main_window)
    if dlg.exec() == QDialog.Accepted:
        ignored = opl_parser.build_from_opl(main_window, dlg.get_opl_text())
        if ignored:
            QMessageBox.information(
                main_window,
                "Import OPL",
                "Některé řádky nebyly rozpoznány a byly přeskočeny:\n\n• " + "\n• ".join(ignored)
            )


def show_nl_to_opl_dialog(main_window):
    """Zobrazí dialog pro NL → OPL generování."""
    dlg = NLtoOPLDialog(main_window, main_window)
    dlg.exec()


def show_opl_preview_dialog(scene, parent=None):
    """Zobrazí dialog s náhledem OPL."""
    dlg = OPLPreviewDialog(scene, parent)
    dlg.exec()

