"""Entry point pro OPM Editor aplikaci."""
from __future__ import annotations
import sys
import traceback

# Nastavení okamžitého výpisu (unbuffered)
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except:
    # Fallback pro starší verze Pythonu
    import functools
    print = functools.partial(print, flush=True)

# Načtení proměnných prostředí ze .env souboru
from dotenv import load_dotenv, find_dotenv
# Qt framework pro GUI
from PySide6.QtWidgets import QApplication, QMessageBox

# Import hlavního okna aplikace a stylů
from ui.main_window import MainWindow
from ui.style import make_light_palette, get_application_stylesheet


def exception_hook(exctype, value, tb):
    """Hook pro zachycení nekontrolovaných výjimek."""
    print("=" * 80)
    print("UNCAUGHT EXCEPTION:")
    print("=" * 80)
    traceback.print_exception(exctype, value, tb)
    print("=" * 80)
    
    # Zobraz dialog s chybou
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))
    QMessageBox.critical(None, "Chyba aplikace", 
                        f"Došlo k neočekávané chybě:\n\n{error_msg}")


def main():
    """Hlavní funkce aplikace - inicializuje a spouští OPM Editor."""
    
    # Nastavení handleru pro nekontrolované výjimky
    sys.excepthook = exception_hook
    
    # Načtení konfigurace z .env souboru (např. API klíče pro AI)
    load_dotenv(find_dotenv(), override=True)
    
    # Vytvoření Qt aplikace (musí být před vytvořením jakýchkoli widgetů)
    app = QApplication(sys.argv)

    # Nastavení světlého vzhledu aplikace
    app.setPalette(make_light_palette())  # Aplikuje světlou barevnou paletu
    app.setStyleSheet(get_application_stylesheet())  # Aplikuje CSS styly pro toolbary a tlačítka
    
    try:
        # Vytvoření a zobrazení hlavního okna editoru
        w = MainWindow()
        w.resize(1100, 700)  # Nastavení výchozí velikosti okna
        w.show()  # Zobrazení okna
        
        # Spuštění Qt event loop a ukončení programu s návratovým kódem
        sys.exit(app.exec())
    except Exception as e:
        print("=" * 80)
        print("FATAL ERROR:")
        print("=" * 80)
        traceback.print_exc()
        print("=" * 80)
        QMessageBox.critical(None, "Fatální chyba", 
                           f"Aplikace nemůže pokračovat:\n\n{str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
