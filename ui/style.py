"""Styly a palety pro aplikaci OPM Editor."""
from PySide6.QtGui import QPalette, QColor


def make_light_palette() -> QPalette:
    """Vytvoří světlou paletu barev pro aplikaci."""
    palette = QPalette()

    def _set_if_available(role_name: str, color: QColor) -> None:
        role = getattr(QPalette, role_name, None)
        if role is not None:
            palette.setColor(role, color)

    # --- základní pozadí ---
    palette.setColor(QPalette.Window, QColor("white"))
    palette.setColor(QPalette.Base, QColor("white"))
    palette.setColor(QPalette.AlternateBase, QColor("#f7f7f7"))
    palette.setColor(QPalette.ToolTipBase, QColor("white"))
    _set_if_available("Menu", QColor("white"))

    # --- texty ---
    palette.setColor(QPalette.WindowText, QColor("black"))  # text v labelech, titulcích
    palette.setColor(QPalette.Text, QColor("black"))        # text v editorech
    palette.setColor(QPalette.ButtonText, QColor("black"))  # text na tlačítkách
    palette.setColor(QPalette.ToolTipText, QColor("black"))
    _set_if_available("PlaceholderText", QColor("#7a7a7a"))
    _set_if_available("MenuText", QColor("black"))

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


def get_application_stylesheet() -> str:
    """Vrátí stylesheet pro aplikaci."""
    return """
        QMainWindow, QWidget {
            background: white;
            color: black;
        }
        QMenuBar {
            background: white;
            color: black;
        }
        QMenuBar::item {
            background: transparent;
            color: black;
            padding: 4px 8px;
        }
        QMenuBar::item:selected {
            background: #eaf2ff;
        }
        QMenu {
            background: white;
            color: black;
            border: 1px solid #d9d9d9;
        }
        QMenu::item:selected {
            background: #eaf2ff;
            color: black;
        }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background: white;
            color: black;
            border: 1px solid #b8b8b8;
            border-radius: 4px;
            padding: 3px 6px;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border: 1px solid #0078d7;
        }
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
    """

