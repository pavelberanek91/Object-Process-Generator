"""Styly a palety pro aplikaci OPM Editor."""
from PySide6.QtGui import QPalette, QColor


def make_light_palette() -> QPalette:
    """Vytvoří světlou paletu barev pro aplikaci."""
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


def get_application_stylesheet() -> str:
    """Vrátí stylesheet pro aplikaci."""
    return """
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

