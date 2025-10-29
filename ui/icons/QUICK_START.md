# 🚀 Rychlý start - Vlastní ikony pro OPM Editor

## Co bylo vytvořeno?

✅ Systém pro načítání vlastních ikon ze souborů SVG/PNG  
✅ Ukázkové ikony pro všechny 4 strukturální vazby  
✅ Dokumentace a návody  
✅ Vizuální preview v HTML  

## 📂 Struktura souborů

```
ui/icons/
├── README.md           ← Kompletní návod na vytváření ikon
├── QUICK_START.md      ← Tento soubor (rychlý start)
├── preview.html        ← Vizuální přehled ikon (otevřete v prohlížeči)
├── aggregation.svg     ← Ikona pro agregaci (vyplněný kosočtverec)
├── exhibition.svg      ← Ikona pro exhibici (prázdný čtverec)
├── generalization.svg  ← Ikona pro generalizaci (prázdný trojúhelník)
└── instantiation.svg   ← Ikona pro instanciaci (vyplněný kruh)
```

## 🎯 Jak to funguje?

1. **Automatické načítání**: Když spustíte OPM Editor, systém automaticky hledá ikony v této složce
2. **Priorita**: `{název}.svg` → `{název}.png` → fallback na generovanou ikonu
3. **Bez konfigurace**: Stačí uložit soubor se správným názvem a restartovat editor

## ✏️ Jak upravit existující ikony?

### Možnost 1: Online editor (nejjednodušší)
1. Otevřete https://svg-edit.github.io/svgedit/
2. File → Open SVG... → vyberte ikonu (např. `aggregation.svg`)
3. Upravte podle potřeby (barvy, tvary, velikosti)
4. File → Save Image... → uložte zpět do `ui/icons/`
5. Restartujte OPM Editor

### Možnost 2: Textový editor
1. Otevřete `.svg` soubor v libovolném textovém editoru
2. SVG je čitelný XML kód - můžete přímo upravovat barvy, čísla, atd.
3. Uložte soubor
4. Restartujte OPM Editor

### Možnost 3: Grafický editor
- **Inkscape** (zdarma): Otevřete SVG → upravte → uložte
- **Figma**: Importujte SVG → upravte → Export as SVG

## 🆕 Jak vytvořit nové ikony?

### Pro ostatní typy vazeb:
Můžete vytvořit ikony i pro procedurální vazby:

```
input.svg           ← Ikona pro input vazbu
consumption.svg     ← Ikona pro consumption vazbu
output.svg          ← Ikona pro output vazbu
result.svg          ← Ikona pro result vazbu
effect.svg          ← Ikona pro effect vazbu
agent.svg           ← Ikona pro agent vazbu
instrument.svg      ← Ikona pro instrument vazbu
```

### Postup:
1. Zkopírujte jednu z existujících SVG ikon jako základ
2. Přejmenujte na nový název (např. `input.svg`)
3. Upravte obsah podle potřeby
4. Uložte a restartujte editor

## 🔍 Kontrola ikon

Otevřete `preview.html` v prohlížeči pro vizuální kontrolu všech ikon:
```bash
# Windows
start ui/icons/preview.html

# Linux/Mac
open ui/icons/preview.html
```

## 🎨 Příklad vlastní ikony

Tady je minimální šablona SVG ikony:

```xml
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <!-- Váš kód zde -->
  <line x1="4" y1="12" x2="20" y2="12" stroke="#000" stroke-width="2"/>
</svg>
```

## ⚠️ Časté problémy

**Ikona se nenačte?**
- ✓ Zkontrolujte název souboru (musí být přesně jako typ vazby, např. `aggregation.svg`)
- ✓ Zkontrolujte, že SVG je validní (otevřete v prohlížeči)
- ✓ Restartovali jste OPM Editor?

**Ikona vypadá špatně?**
- ✓ Zkontrolujte rozměry (`viewBox="0 0 24 24"`)
- ✓ Použijte vhodnou tloušťku čar (2-3 px)
- ✓ Zkontrolujte barvu (černá nebo tmavě šedá)

**Chci vrátit původní ikony?**
- Jednoduše smažte nebo přejmenujte SVG soubor
- Editor automaticky použije fallback (generovanou ikonu)

## 📚 Další informace

Přečtěte si `README.md` pro:
- Detailní specifikace ikon
- Tipy a triky pro návrh
- Reference na SVG tutoriály
- Další pokročilé možnosti

## 🎉 A je to!

Nyní můžete přizpůsobit ikony podle vašich preferencí. Stačí upravit SVG soubory a restartovat editor!

