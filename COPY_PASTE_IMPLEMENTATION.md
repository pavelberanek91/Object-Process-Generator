# Copy-Paste & Duplicate - Implementační souhrn

## Přehled implementace

Byl implementován kompletní systém pro kopírování, vkládání a duplikaci prvků v OPM diagramech.

## Změněné soubory

### 1. `undo/commands.py`
**Přidáno:**
- Import `next_id` z `utils.ids`
- Import `Dict` z `typing`
- Nová třída `PasteItemsCommand` (řádky 410-560)
  - Implementuje undo/redo pro vkládání prvků
  - Vytváří nové kopie uzlů a linků s novými ID
  - Podporuje offset při vkládání
  - Správně kopíruje objekty včetně jejich stavů
  - Kopíruje vazby pouze mezi vybranými uzly

### 2. `ui/main_window.py`
**Přidáno:**
- Import `PasteItemsCommand` z `undo.commands`
- Instance proměnná `self.clipboard = None` (řádek 63)
- Klávesové zkratky v `_init_actions()`:
  - Copy: `Ctrl+C` / `Cmd+C`
  - Paste: `Ctrl+V` / `Cmd+V`
  - Duplicate: `Ctrl+D` / `Cmd+D`
- Nové metody:
  - `copy_selection()` - kopíruje vybrané prvky do schránky
  - `paste_selection()` - vkládá prvky ze schránky
  - `duplicate_selection()` - duplikuje vybrané prvky
  - `_serialize_node()` - serializuje uzel do slovníku
  - `_serialize_state()` - serializuje stav do slovníku
  - `_serialize_link()` - serializuje vazbu do slovníku

## Architektura

### Clipboard systém
- **Interní schránka**: Data uložena v `MainWindow.clipboard`
- **Formát**: Slovník s klíči `"nodes"` a `"links"`
- **Perzistence**: Data zůstávají až do dalšího kopírování

### Kopírování (Copy)
1. Sesbírá všechny vybrané uzly (ObjectItem, ProcessItem)
2. Automaticky přidá stavy vybraných objektů
3. Najde všechny linky mezi vybranými uzly
4. Serializuje data do slovníku
5. Uloží do `self.clipboard`

### Vkládání (Paste)
1. Kontroluje, zda je schránka neprázdná
2. Vytvoří `PasteItemsCommand` s offsetem
3. Pushne příkaz na undo stack (volá `redo()`)
4. `PasteItemsCommand.redo()`:
   - Vytvoří nové kopie uzlů s novými ID
   - Posune je o offset (default 30x30)
   - Zkopíruje i stavy objektů
   - Vytvoří nové linky mezi vloženými uzly
   - Přidá vše do scény
5. Označí vložené prvky
6. Synchronizuje s globálním modelem

### Duplikace (Duplicate)
- Jednoduchá kombinace `copy_selection()` + `paste_selection()`

### Undo/Redo podpora
- `PasteItemsCommand` implementuje `undo()` a `redo()`
- Při undo: odstraní vložené prvky ze scény
- Při redo: přidá stejné prvky zpět (bez nového vytváření)
- Plná synchronizace s globálním modelem

## Technické detaily

### Generování nových ID
- Každý nový prvek dostává ID pomocí `next_id(kind)`
- Mapování starých ID → nových ID v `id_mapping`
- Zaručuje unikátnost ID napříč diagramem

### Kopírování stavů
- Stavy jsou automaticky kopírovány s jejich rodičovským objektem
- Pozice stavu je relativní k objektu (lokální souřadnice)
- Parent-child vztah je zachován

### Kopírování vazeb
- Vazba se kopíruje pouze pokud jsou oba uzly (src, dst) ve výběru
- Zachovává typ vazby (link_type)
- Zachovává label a kardinality (card_src, card_dst)

### Parent Process ID
- Při vkládání se zachovává `parent_process_id`
- Prvky zůstávají ve stejném in-zoom view
- Správná synchronizace s globálním modelem

## Testování

### Manuální test
1. Spusťte aplikaci: `python app.py`
2. Vytvořte několik objektů a procesů
3. Vytvořte vazby mezi nimi
4. Označte některé prvky
5. Stiskněte `Ctrl+C` pro kopírování
6. Stiskněte `Ctrl+V` pro vložení
7. Ověřte, že nové prvky:
   - Mají offset od originálu
   - Mají nové ID
   - Zachovávají vazby mezi sebou
8. Stiskněte `Ctrl+Z` pro undo
9. Ověřte, že vložené prvky zmizely
10. Stiskněte `Ctrl+Y` pro redo
11. Ověřte, že prvky se vrátily

### Test duplikace
1. Označte prvky
2. Stiskněte `Ctrl+D`
3. Ověřte okamžitou duplikaci

### Test objektů se stavy
1. Vytvořte objekt
2. Přidejte několik stavů (double-click na objekt)
3. Označte objekt
4. Stiskněte `Ctrl+C` a `Ctrl+V`
5. Ověřte, že nový objekt obsahuje kopie všech stavů

## Známá omezení

1. **Interní schránka**: Nelze kopírovat mezi instancemi aplikace
2. **Systémová schránka**: Není použita (budoucí vylepšení)
3. **Cross-view paste**: Při vkládání do jiného in-zoom view může dojít k neočekávanému chování (zachovává parent_process_id)

## Budoucí vylepšení

1. Integrace se systémovou schránkou
2. Export/import do JSON formátu
3. Chytrý paste (automatická detekce cílového view)
4. Paste na pozici kurzoru myši
5. Multi-paste (opakované vkládání stejných dat)

