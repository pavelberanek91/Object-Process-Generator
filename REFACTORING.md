# Refactoring dokumentace

## Přehled změn

Byla provedena rozsáhlá refaktorizace kódové báze s cílem zlepšit čitelnost, udržovatelnost a oddělení zodpovědností.

## Původní stav

- **app.py**: Monolitický soubor s 802 řádky obsahující vše (MainWindow, dialogy, toolbary, styly, main funkce)

## Nová struktura

### 1. `ui/style.py`
- **Účel**: Správa stylů a palet aplikace
- **Funkce**:
  - `make_light_palette()`: Vytváří světlou barevnou paletu
  - `get_application_stylesheet()`: Vrací stylesheet pro toolbar a další widgety

### 2. `ui/properties_panel.py`
- **Účel**: Properties panel jako samostatný dock widget
- **Třída**: `PropertiesPanel(QDockWidget)`
- **Zodpovědnosti**:
  - Zobrazení vlastností vybraných prvků (Objects, Processes, States, Links)
  - Editace labelů, typů linků a kardinalit
  - Generování OPL náhledu

### 3. `ui/toolbar.py`
- **Účel**: Správa toolbarů
- **Třída**: `ToolbarManager`
- **Zodpovědnosti**:
  - Vytváření hlavního toolbaru (File menu, Export menu, Mode actions)
  - Vytváření Edit toolbaru (Undo/Redo)
  - Správa akcí a tlačítek

### 4. `ui/dialogs.py`
- **Účel**: Všechny dialogy aplikace
- **Třídy**:
  - `OPLImportDialog`: Dialog pro import OPL
  - `NLtoOPLDialog`: Dialog pro generování OPL z přirozeného jazyka
  - `OPLPreviewDialog`: Dialog pro náhled a export OPL
- **Funkce**:
  - `show_opl_import_dialog()`: Zobrazí OPL import dialog
  - `show_nl_to_opl_dialog()`: Zobrazí NL→OPL dialog
  - `show_opl_preview_dialog()`: Zobrazí OPL preview dialog

### 5. `ui/main_window.py`
- **Účel**: Hlavní okno aplikace
- **Třída**: `MainWindow(QMainWindow)`
- **Zodpovědnosti**:
  - Správa tabů a canvasů
  - Správa módu editoru (SELECT, ADD_OBJECT, ADD_PROCESS, ADD_STATE, ADD_LINK)
  - Operace s uzly (add_object, add_process, add_state)
  - Operace s linky (handle_link_click, allowed_link)
  - Delete operace (delete_selected, clear_all)
  - Export obrázků (JPG, PNG, SVG)
  - Zoom operace
  - Keyboard events

### 6. `app.py`
- **Účel**: Entry point aplikace
- **Obsah**: Pouze `main()` funkce
- **Zodpovědnosti**:
  - Inicializace QApplication
  - Nastavení stylů a palet
  - Vytvoření a zobrazení hlavního okna

## Výhody refaktoringu

### 1. **Separation of Concerns**
- Každý modul má jasně definovanou zodpovědnost
- Snadnější orientace v kódu

### 2. **Maintainability**
- Změny v UI komponentách jsou izolované
- Snadnější testování jednotlivých částí

### 3. **Reusability**
- Dialogy a panely lze snadno použít jinde
- ToolbarManager je konfigurovatelný

### 4. **Readability**
- Kratší soubory (každý pod 300 řádků)
- Logické seskupení funkcí

### 5. **Scalability**
- Snadné přidávání nových dialogů nebo panelů
- Lepší struktura pro budoucí rozšíření

## Struktura složky `ui/`

```
ui/
├── __init__.py
├── dialogs.py          # Všechny dialogy
├── icons.py            # Ikony (existující)
├── main_window.py      # Hlavní okno
├── properties_panel.py # Properties panel
├── style.py            # Styly a palety
├── tabs.py             # Tab bar (existující)
├── toolbar.py          # Toolbar management
└── view.py             # Editor view (existující)
```

## Migrace z původního kódu

Pokud máte kód odkazující na staré umístění, použijte tyto aktualizace:

### Import MainWindow
```python
# Staré
from app import MainWindow

# Nové
from ui.main_window import MainWindow
```

### Import funkcí
```python
# Staré
from app import make_light_palette

# Nové
from ui.style import make_light_palette
```

## Zpětná kompatibilita

Refaktoring **nezměnil**:
- API MainWindow třídy (všechny metody zůstaly stejné)
- Chování aplikace
- UI/UX
- Formáty exportovaných souborů

## Testování

Aplikace byla testována a spouští se bez chyb:
```bash
python app.py
```

## Další možná vylepšení

1. Přidat unit testy pro jednotlivé moduly
2. Vytvořit configuration manager pro nastavení
3. Přesunout konstanty do config souboru
4. Přidat logging
5. Dokumentovat API jednotlivých tříd

