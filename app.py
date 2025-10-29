"""Entry point pro OPM Editor aplikaci."""
from __future__ import annotations
import sys

# Načtení proměnných prostředí ze .env souboru
from dotenv import load_dotenv, find_dotenv
# Qt framework pro GUI
from PySide6.QtWidgets import QApplication

# Import hlavního okna aplikace a stylů
from ui.main_window import MainWindow
from ui.style import make_light_palette, get_application_stylesheet


def main():
    """Hlavní funkce aplikace - inicializuje a spouští OPM Editor."""
    
    # Načtení konfigurace z .env souboru (např. API klíče pro AI)
    load_dotenv(find_dotenv(), override=True)
    
    # Vytvoření Qt aplikace (musí být před vytvořením jakýchkoli widgetů)
    app = QApplication(sys.argv)

    # Nastavení světlého vzhledu aplikace
    app.setPalette(make_light_palette())  # Aplikuje světlou barevnou paletu
    app.setStyleSheet(get_application_stylesheet())  # Aplikuje CSS styly pro toolbary a tlačítka
    
    # Vytvoření a zobrazení hlavního okna editoru
    w = MainWindow()
    w.resize(1100, 700)  # Nastavení výchozí velikosti okna
    w.show()  # Zobrazení okna
    
    # Spuštění Qt event loop a ukončení programu s návratovým kódem
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
