# Návod na vytváření vlastních ikon pro OPM Editor

Tato složka obsahuje vlastní ikony pro strukturální vazby a další prvky editoru.

## 📁 Struktura

Ikony se ukládají přímo do této složky (`ui/icons/`) s názvem odpovídajícím typu vazby:

```
ui/icons/
├── README.md           # tento soubor
├── aggregation.svg     # ikona pro agregaci
├── exhibition.svg      # ikona pro exhibici
├── generalization.svg  # ikona pro generalizaci
└── instantiation.svg   # ikona pro instanciaci
```

## 🎨 Formáty souborů

Editor podporuje dva formáty:
- **SVG** (doporučeno) - vektorový formát, škáluje se bez ztráty kvality
- **PNG** - rastrový formát, použije se pokud SVG neexistuje

Priorita načítání: `{název}.svg` → `{název}.png` → generovaná ikona v kódu

## 📐 Specifikace ikon

### Rozměry
- **Velikost plátna**: 24×24 px (nebo 22×22 px)
- **Aktivní oblast**: doporučeno 18×18 px (3px okraj)
- **Tloušťka čar**: 2-3 px pro dobrou viditelnost

### Styly
- **Barva**: černá (`#000000`) nebo tmavě šedá (`#333333`)
- **Pozadí**: průhledné
- **Anti-aliasing**: zapnutý
- **Styl**: jednoduchý, minimalistický

## 🔧 Jak vytvořit ikony

### Možnost 1: Pomocí online editoru
1. Otevřete [SVG-Edit](https://svg-edit.github.io/svgedit/) nebo [Boxy SVG](https://boxy-svg.com/app)
2. Vytvořte nový dokument 24×24 px
3. Nakreslete ikonu podle specifikace níže
4. Exportujte jako SVG
5. Uložte do této složky s příslušným názvem

### Možnost 2: Pomocí designového nástroje
- **Inkscape** (zdarma): File → Document Properties → nastavte 24×24 px
- **Figma** (online): vytvořte frame 24×24 px, exportujte jako SVG
- **Adobe Illustrator**: nastavte artboard 24×24 px

### Možnost 3: Použít dodané šablony
V této složce najdete šablonové soubory `*.svg`, které můžete upravit podle potřeby.

## 📋 Návrhy ikon pro strukturální vazby

### Aggregation (agregace)
**Symbol**: vyplněný kosočtverec (diamant) + čára
- Kosočtverec 10×10 px, vyplněný černě
- Čára vedoucí z kosočtverce doprava

### Exhibition (exhibice)  
**Symbol**: prázdný čtverec + čára
- Čtverec 10×10 px, pouze obrys (2px)
- Čára vedoucí z čtverce doprava

### Generalization (generalizace)
**Symbol**: prázdný trojúhelník + čára
- Rovnoramenný trojúhelník, pouze obrys (2px)
- Čára vedoucí z trojúhelníku doleva (opačně než ostatní)

### Instantiation (instanciace)
**Symbol**: vyplněný kruh + čára
- Kruh průměr 10 px, vyplněný černě
- Čára vedoucí z kruhu doprava

## 🔍 Příklad SVG kódu

Zde je základní šablona SVG ikony:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">
  <!-- Pozadí průhledné -->
  
  <!-- Čára -->
  <line x1="4" y1="12" x2="14" y2="12" 
        stroke="#000000" stroke-width="2" 
        stroke-linecap="round"/>
  
  <!-- Symbol (např. kosočtverec pro aggregation) -->
  <path d="M 20 12 L 16 8 L 12 12 L 16 16 Z" 
        fill="#000000" stroke="#000000" stroke-width="1"/>
</svg>
```

## ✅ Testování

Po vytvoření ikony:
1. Uložte soubor do `ui/icons/{název}.svg`
2. Restartujte OPM Editor
3. Ikona se automaticky načte a zobrazí v toolbaru

Pokud ikona není načtená:
- Zkontrolujte název souboru (musí odpovídat typu vazby)
- Zkontrolujte, že SVG je validní (otevřete v prohlížeči)
- Zkontrolujte console pro případné chyby

## 🎯 Tipy a triky

- Používejte **viewBox** místo absolutních rozměrů pro lepší škálovatelnost
- Používejte **stroke-linecap="round"** pro hezčí zakončení čar
- Optimalizujte SVG pomocí [SVGOMG](https://jakearchibald.github.io/svgomg/)
- Inspirujte se existujícími ikonami z `ui/icons.py` (funkce `_draw_marker()`)

## 📚 Další zdroje

- [SVG Tutorial (MDN)](https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial)
- [SVG Path Reference](https://www.w3.org/TR/SVG/paths.html)
- [Qt SVG Documentation](https://doc.qt.io/qt-6/qsvgrenderer.html)

