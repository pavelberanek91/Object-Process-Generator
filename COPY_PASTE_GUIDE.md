# Copy-Paste & Duplicate - Průvodce použitím

## Nové funkce

Aplikace nyní podporuje kopírování, vkládání a duplikaci prvků v diagramech.

## Klávesové zkratky

### Copy (Kopírovat)
- **Windows/Linux**: `Ctrl+C`
- **macOS**: `Cmd+C`

Zkopíruje vybrané prvky do schránky.

### Paste (Vložit)
- **Windows/Linux**: `Ctrl+V`
- **macOS**: `Cmd+V`

Vloží zkopírované prvky ze schránky s offsetem 30x30 pixelů od originálu.

### Duplicate (Duplikovat)
- **Windows/Linux**: `Ctrl+D`
- **macOS**: `Cmd+D`

Zkopíruje a ihned vloží vybrané prvky (kombinace Copy + Paste).

## Co se kopíruje?

### Podporované prvky
- **Objekty** (ObjectItem) - včetně jejich stavů
- **Procesy** (ProcessItem)
- **Stavy** (StateItem) - pokud je vybraný i jejich rodičovský objekt
- **Vazby** (LinkItem) - pouze vazby mezi vybranými uzly

### Vlastnosti prvků, které se kopírují
- Label (název)
- Pozice (s offsetem při vkládání)
- Velikost (šířka, výška)
- Essence (physical/informatical)
- Affiliation (systemic/environmental)
- Parent process ID (pro in-zoom views)
- Kardinality vazeb (card_src, card_dst)

## Jak to funguje?

1. **Výběr prvků**: Označte prvky, které chcete zkopírovat
   - Kliknutím s myší
   - Nebo tažením (rubber band selection)
   - Nebo pomocí `Ctrl+A` (Select All)

2. **Kopírování**: Stiskněte `Ctrl+C` (nebo `Cmd+C` na macOS)
   - Prvky jsou uloženy do interní schránky aplikace
   - Status bar zobrazí počet zkopírovaných prvků a vazeb

3. **Vkládání**: Stiskněte `Ctrl+V` (nebo `Cmd+V` na macOS)
   - Nové prvky se vytvoří s novými ID
   - Prvky jsou posunuty o 30 pixelů doprava a dolů
   - Vložené prvky jsou automaticky označeny
   - Status bar zobrazí počet vložených prvků

4. **Undo/Redo**: Copy-paste podporuje plně undo/redo
   - `Ctrl+Z` - vrátí vložení zpět
   - `Ctrl+Y` nebo `Ctrl+Shift+Z` - opakuje vložení

## Příklady použití

### Kopírování jednoho objektu
1. Klikněte na objekt pro výběr
2. Stiskněte `Ctrl+C`
3. Stiskněte `Ctrl+V`
4. Nový objekt se objeví s offsetem

### Kopírování více prvků
1. Podržte `Shift` a klikněte na více prvků
2. Nebo použijte rubber band selection (táhněte myší)
3. Stiskněte `Ctrl+C`
4. Stiskněte `Ctrl+V`

### Rychlá duplikace
1. Označte prvky
2. Stiskněte `Ctrl+D`
3. Prvky jsou okamžitě zduplikovány

### Kopírování objektu se stavy
1. Označte objekt (stavy se automaticky zkopírují)
2. Stiskněte `Ctrl+C`
3. Stiskněte `Ctrl+V`
4. Nový objekt obsahuje kopie všech stavů

### Kopírování struktury s vazbami
1. Označte více uzlů (objekty/procesy)
2. Označte i vazby mezi nimi (klikněte s `Shift`)
3. Stiskněte `Ctrl+C`
4. Stiskněte `Ctrl+V`
5. Celá struktura je zkopírována včetně vazeb

## Poznámky

- Schránka je interní (nelze kopírovat mezi instancemi aplikace)
- Linky se kopírují pouze pokud jsou oba konce (src a dst) ve výběru
- Při vkládání se všechny ID generují nově (žádné kolize)
- Parent process ID zůstává zachován (vložené prvky patří do stejného in-zoom view)
- Stavy jsou vždy vázány na svůj rodičovský objekt

