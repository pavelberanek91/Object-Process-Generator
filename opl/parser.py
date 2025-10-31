"""Parser OPL vět - převádí textové OPL věty na diagram (uzly a vazby)."""
from __future__ import annotations
from typing import Dict, List
from PySide6.QtCore import QPointF, QRectF
from graphics.nodes import ObjectItem, ProcessItem, StateItem
from graphics.link import LinkItem
from constants import NODE_W, NODE_H, STATE_W, STATE_H
from opl.regexes import *  # Import všech regexových vzorů


def _norm(name: str) -> str:
    """
    Normalizuje název - odstraní přebytečné mezery a uvozovky.
    
    Args:
        name: Surový název z OPL věty
    
    Returns:
        Vyčištěný název
    """
    return name.strip().strip('"')


def _split_names(s: str) -> List[str]:
    """
    Rozdělí seznam názvů oddělených čárkami a "and"/"or" na jednotlivé položky.
    
    Používá se pro seznam objektů/procesů.
    Příklad: "A, B and C" → ["A", "B", "C"]
    
    Args:
        s: Text obsahující seznam názvů
    
    Returns:
        Seznam jednotlivých názvů (bez duplicit)
    """
    s = s.strip().strip(".")
    # Nahradí "and" i "or" čárkou pro jednotné zpracování
    s = re.sub(r"\s+(?:and|or)\s+", ", ", s, flags=re.I)
    parts = [p.strip().strip('"') for p in s.split(",")]
    # Odstranění duplicit při zachování pořadí
    return list(dict.fromkeys([p for p in parts if p]))


def _split_states(s: str) -> List[str]:
    """
    Rozdělí seznam stavů oddělených čárkami a "or" na jednotlivé položky.
    
    Používá se pro seznam stavů (které jsou spojeny "or", ne "and").
    Příklad: "Pending, Confirmed or Delivered" → ["Pending", "Confirmed", "Delivered"]
    
    Args:
        s: Text obsahující seznam stavů
    
    Returns:
        Seznam jednotlivých stavů (bez duplicit)
    """
    s = s.strip().strip(".")
    # Nahradí pouze "or" čárkou (stavy nejsou spojeny "and")
    s = re.sub(r"\s+or\s+", ", ", s, flags=re.I)
    parts = [p.strip().strip('"') for p in s.split(",")]
    # Odstranění duplicit při zachování pořadí
    return list(dict.fromkeys([p for p in parts if p]))


def get_or_create_state(obj, label: str):
    """
    Vrátí existující stav objektu, nebo vytvoří nový.
    
    Args:
        obj: ObjectItem, do kterého stav patří
        label: Název stavu
    
    Returns:
        StateItem s daným názvem
    """
    # Hledá existující stav mezi potomky objektu
    for child in obj.childItems():
        if isinstance(child, StateItem) and child.label == label:
            return child
    
    # Pokud stav neexistuje, vytvoří nový s výchozí velikostí
    rect = QRectF(-50, -14, 100, 28)  # Výchozí velikost stavu
    item = StateItem(obj, rect, label)
    obj.scene().addItem(item)
    return item


def build_from_opl(app, text: str):
    """
    Postaví/rozšíří diagram v 'app.scene' na základě OPL vět v textu.
    
    Parsuje text řádek po řádku, rozpoznává OPL věty pomocí regexů
    a vytváří odpovídající uzly (objekty, procesy, stavy) a vazby.
    
    Args:
        app: Reference na hlavní aplikaci (potřebuje app.scene a app.snap)
        text: Text obsahující OPL věty (každá věta na samostatném řádku)
    
    Returns:
        Seznam ignorovaných řádků (nepodařilo se rozpoznat)
    """
    scene = app.scene
    
    # === Inicializace cache existujících prvků ===
    # Mapování label → item pro rychlé vyhledání existujících uzlů
    by_label: Dict[str, object] = {}
    # Mapování label → kind ("object"/"process") pro rozlišení typu
    kind_of: Dict[str, str] = {}
    # Mapování label → essence ("physical"/"informatical")
    essence_of: Dict[str, str] = {}
    # Mapování label → affiliation ("systemic"/"environmental")
    affiliation_of: Dict[str, str] = {}
    
    # Projde existující uzly ve scéně a uloží je do cache
    for it in scene.items():
        if isinstance(it, (ObjectItem, ProcessItem)):
            by_label[it.label] = it
            kind_of[it.label] = it.kind
            # Pro objekty je výchozí essence "informatical", pro procesy "physical"
            default_essence = 'informatical' if isinstance(it, ObjectItem) else 'physical'
            essence_of[it.label] = getattr(it, 'essence', default_essence)
            affiliation_of[it.label] = getattr(it, 'affiliation', 'systemic')

    # === Určení pozice pro nové prvky ===
    # Nové prvky se umístí vpravo od existujícího diagramu
    items_rect = scene.itemsBoundingRect() if scene.items() else QRectF(-200, -150, 400, 300)
    base_x = items_rect.right() + 150  # X souřadnice "nové oblasti"
    proc_i = 0  # Index pro rozestup procesů
    obj_i = 0   # Index pro rozestup objektů

    def next_proc_pos():
        """Vrátí další pozici pro nový proces (nahoře v řadě)."""
        nonlocal proc_i
        p = app.snap(QPointF(base_x + proc_i * 200, -150))
        proc_i += 1
        return p

    def next_obj_pos():
        """Vrátí další pozici pro nový objekt (dole v řadě)."""
        nonlocal obj_i
        p = app.snap(QPointF(base_x + obj_i * 200, 130))
        obj_i += 1
        return p

    def get_or_create_process(name: str):
        """Vrátí existující proces nebo vytvoří nový."""
        name = _norm(name)
        it = by_label.get(name)
        # Pokud již existuje jako proces, vrátí ho
        if it and isinstance(it, ProcessItem):
            return it
        # Pokud existuje jako objekt, vrátí objekt (nechceme duplikáty)
        if it and isinstance(it, ObjectItem):
            return it
        # Vytvoří nový proces s atributy z definice (pokud existují)
        essence = essence_of.get(name, "physical")
        affiliation = affiliation_of.get(name, "systemic")
        item = ProcessItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H), name, essence, affiliation)
        item.setPos(next_proc_pos())
        scene.addItem(item)
        by_label[name] = item
        kind_of[name] = "process"
        return item

    def get_or_create_object(name: str):
        """Vrátí existující objekt nebo vytvoří nový."""
        name = _norm(name)
        it = by_label.get(name)
        # Pokud již existuje jako objekt, vrátí ho
        if it and isinstance(it, ObjectItem):
            return it
        # Pokud existuje jako proces, vrátí proces (nechceme duplikáty)
        if it and isinstance(it, ProcessItem):
            return it
        # Vytvoří nový objekt s atributy z definice (pokud existují)
        essence = essence_of.get(name, "informatical")
        affiliation = affiliation_of.get(name, "systemic")
        item = ObjectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H), name, essence, affiliation)
        item.setPos(next_obj_pos())
        scene.addItem(item)
        by_label[name] = item
        kind_of[name] = "object"
        return item

    def ensure_link(src, dst, lt: str, label: str = ""):
        """
        Zajistí, že vazba mezi src a dst existuje. Pokud ano, vrátí ji; pokud ne, vytvoří.
        
        Args:
            src: Zdrojový uzel
            dst: Cílový uzel
            lt: Typ vazby (link_type)
            label: Volitelný popisek vazby
        
        Returns:
            LinkItem nebo None (pokud vazba není povolena)
        """
        # Hledá existující vazbu se stejným zdrojem, cílem a typem
        for it in scene.items():
            if isinstance(it, LinkItem) and it.src is src and it.dst is dst and it.link_type == lt:
                return it
        
        # Zkontroluj, zda je vazba povolena
        ok, msg = app.allowed_link(src, dst, lt)
        if not ok:
            # Vazba není povolena, ignorujeme ji
            ignored.append(f"Vazba ignorována: {msg}")
            return None
        
        # Vytvoří novou vazbu
        ln = LinkItem(src, dst, lt, label)
        scene.addItem(ln)
        return ln

    # Seznam nerozpoznaných řádků (pro informaci uživateli)
    ignored: List[str] = []

    # === PRVNÍ PRŮCHOD: Zpracování definic objektů a procesů ===
    # Definice musí být zpracovány jako první, aby byly atributy k dispozici
    # při vytváření uzlů v druhém průchodu
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        
        # Zpracování definic s essence a affiliation
        # Příklad: "A is a informatical and systemic object."
        # Příklad: "A is a systemic and informatical object."
        m = RE_DEFINITION.match(line)
        if m:
            name = _norm(m.group("name"))
            # Extraktujeme atributy - podporujeme obě pořadí
            if m.group("essence1"):
                essence = m.group("essence1").lower()
                affiliation = m.group("affiliation1").lower()
            else:
                essence = m.group("essence2").lower()
                affiliation = m.group("affiliation2").lower()
            kind = m.group("kind").lower()
            
            # Uložíme atributy pro použití při vytváření uzlu
            essence_of[name] = essence
            affiliation_of[name] = affiliation
            kind_of[name] = kind
            
            # Pokud uzel už existuje, aktualizujeme jeho atributy
            it = by_label.get(name)
            if it and isinstance(it, (ObjectItem, ProcessItem)):
                it.essence = essence
                it.affiliation = affiliation
                it.update()
            else:
                # Vytvoříme nový uzel přímo
                if kind == "object":
                    item = ObjectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H), name, essence, affiliation)
                    item.setPos(next_obj_pos())
                    scene.addItem(item)
                    by_label[name] = item
                elif kind == "process":
                    item = ProcessItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H), name, essence, affiliation)
                    item.setPos(next_proc_pos())
                    scene.addItem(item)
                    by_label[name] = item
            continue
        
        # Zpracování definic s jedním atributem
        # Příklad: "Car is an informatical object." (affiliation=systemic implicitní)
        # Příklad: "Car is a systemic object." (essence=informatical implicitní pro objekty)
        m = RE_DEFINITION_SINGLE.match(line)
        if m:
            name = _norm(m.group("name"))
            attr_raw = m.group("attr")  # Surový atribut (nechceme .lower() hned, potřebujeme zkontrolovat velikost písmen)
            kind = m.group("kind").lower()
            
            # Kontrola: pokud atribut začíná velkým písmenem, jde o generalizaci, ne o definici atributu
            # Toto je důležité pro rozlišení "Car is an Informatical object." (generalizace)
            # od "Car is an informatical object." (definice atributu)
            if attr_raw and attr_raw[0].isupper():
                # Není to definice atributu, ale generalizace - přeskočíme to zde,
                # bude zpracováno v druhém průchodu jako RE_IS_A
                continue
            
            # Atribut je malými písmeny, takže jde o definici atributu
            attr = attr_raw.lower()
            
            # Určíme, zda je to essence nebo affiliation
            if attr in ("physical", "informatical"):
                # Je to essence
                essence = attr
                # Implicitní affiliation
                affiliation = "systemic"
            elif attr in ("systemic", "environmental"):
                # Je to affiliation
                affiliation = attr
                # Implicitní essence podle typu
                if kind == "object":
                    essence = "informatical"
                else:  # process
                    essence = "physical"
            else:
                # Neznámý atribut - přeskočíme
                continue
            
            # Uložíme atributy pro použití při vytváření uzlu
            essence_of[name] = essence
            affiliation_of[name] = affiliation
            kind_of[name] = kind
            
            # Pokud uzel už existuje, aktualizujeme jeho atributy
            it = by_label.get(name)
            if it and isinstance(it, (ObjectItem, ProcessItem)):
                it.essence = essence
                it.affiliation = affiliation
                it.update()
            else:
                # Vytvoříme nový uzel přímo
                if kind == "object":
                    item = ObjectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H), name, essence, affiliation)
                    item.setPos(next_obj_pos())
                    scene.addItem(item)
                    by_label[name] = item
                elif kind == "process":
                    item = ProcessItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H), name, essence, affiliation)
                    item.setPos(next_proc_pos())
                    scene.addItem(item)
                    by_label[name] = item
            continue

    # === DRUHÝ PRŮCHOD: Parsování ostatních OPL vět řádek po řádku ===
    for raw in text.splitlines():
        line = raw.strip()
        if not line:  # Prázdné řádky přeskočíme
            continue
        
        # Přeskočíme definice (už byly zpracovány v prvním průchodu)
        if RE_DEFINITION.match(line):
            continue

        # === Consumption - proces spotřebovává objekt (nebo objekt ve stavu) ===
        # Příklad: "Manufacturing consumes Material." nebo "Manufacturing consumes Material at state Raw."
        m = RE_CONSUMES.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            obj = get_or_create_object(m.group("obj"))
            state = m.group("state")  # Volitelný stav
            if state:
                # Spotřebovává konkrétní stav objektu
                s_item = get_or_create_state(obj, state)
                ensure_link(s_item, p, "consumption")
            else:
                # Spotřebovává celý objekt
                ensure_link(obj, p, "consumption")
            continue

        # === Input - proces bere objekty jako vstup ===
        # Příklad: "Processing takes A, B and C as input."
        m = RE_INPUTS.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            # Může být více objektů oddělených čárkami a "and"
            for o in _split_names(m.group("objs")):
                ensure_link(get_or_create_object(o), p, "consumption")
            continue

        # === Yield/Result - proces vytváří objekty ===
        # Příklad: "Manufacturing yields Product."
        # Příklad: "Machining yields Part at state pre-tested."
        m = RE_YIELDS.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            obj_name = _norm(m.group("obj"))
            state = m.group("state")  # Volitelný stav
            obj = get_or_create_object(obj_name)
            
            if state:
                # Vytváří konkrétní stav objektu
                s_item = get_or_create_state(obj, state)
                ensure_link(p, s_item, "result")
            else:
                # Vytváří celý objekt
                ensure_link(p, obj, "result")
            continue

        # === Agent - kdo řídí proces ===
        # Příklad: "Worker handles Manufacturing."
        m = RE_HANDLES.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            # Může být více agentů
            for a in _split_names(m.group("agents")):
                ensure_link(get_or_create_object(a), p, "agent")
            continue

        # === Instrument - proces vyžaduje nástroje/zdroje ===
        # Příklad: "Manufacturing requires Tools."
        m = RE_REQUIRES.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            # Může vyžadovat více instrumentů
            for ins in _split_names(m.group("objs")):
                ensure_link(get_or_create_object(ins), p, "instrument")
            continue

        # === Effect - proces/objekt ovlivňuje jiné objekty ===
        # Příklad: "Temperature affects Quality." nebo "Processing affects Product."
        m = RE_AFFECTS.match(line)
        if m:
            x = _norm(m.group("x"))
            y = _norm(m.group("y"))
            # Heuristika: pokud známe typ z předchozích vět, použijeme ho
            if kind_of.get(x) == "process" or kind_of.get(y) == "object":
                ensure_link(get_or_create_process(x), get_or_create_object(y), "effect")
            elif kind_of.get(x) == "object" or kind_of.get(y) == "process":
                ensure_link(get_or_create_object(x), get_or_create_process(y), "effect")
            else:
                # Výchozí: X je proces, Y je objekt
                ensure_link(get_or_create_process(x), get_or_create_object(y), "effect")
            continue

        # === Aggregation - objekt se skládá z částí ===
        # Příklad: "Car consists of Engine, Wheels and Body."
        # Poznámka: Link vytváříme jako part → whole (protože generátor prohodí src↔dst pro strukturální vazby)
        m = RE_COMPOSED.match(line)
        if m:
            whole = get_or_create_object(m.group("whole"))
            # Může se skládat z více částí
            for part in _split_names(m.group("parts")):
                ensure_link(get_or_create_object(part), whole, "aggregation")
            continue

        # === Characterization - objekt je charakterizován atributy ===
        # Příklad: "Person is characterized by Name and Age."
        m = RE_CHARAC.match(line)
        if m:
            obj = get_or_create_object(m.group("obj"))
            # Může mít více atributů
            for attr in _split_names(m.group("attrs")):
                ensure_link(obj, get_or_create_object(attr), "characterization")
            continue

        # === Exhibition - objekt vykazuje vlastnosti ===
        # Příklad: "Product exhibits Quality and Price."
        # Poznámka: Link vytváříme jako attr → obj (protože generátor prohodí src↔dst pro strukturální vazby)
        m = RE_EXHIBITS.match(line)
        if m:
            obj = get_or_create_object(m.group("obj"))
            # Může vykazovat více vlastností
            for attr in _split_names(m.group("attrs")):
                ensure_link(get_or_create_object(attr), obj, "exhibition")
            continue

        # === Generalization - nadřazená třída generalizuje podtřídy ===
        # Příklad: "Vehicle generalizes Car and Bike."
        m = RE_GENER.match(line)
        if m:
            sup = get_or_create_object(m.group("super"))
            # Může generalizovat více podtříd
            for sub in _split_names(m.group("subs")):
                ensure_link(get_or_create_object(sub), sup, "generalization")
            continue

        # === Generalization - alternativní syntaxe (podtřídy "are" nadřazená třída) ===
        # Příklad: "Freezing, Dehydrating, and Canning are Spoilage Slowing."
        m = RE_ARE.match(line)
        if m:
            sup = get_or_create_object(m.group("super"))
            # Může být více podtříd oddělených čárkami a "and"
            for sub in _split_names(m.group("subs")):
                ensure_link(get_or_create_object(sub), sup, "generalization")
            continue

        # === Instantiation - třída má konkrétní instance ===
        # Příklad: "Person has instances John, Mary and Bob."
        m = RE_INSTANCES.match(line)
        if m:
            cls = get_or_create_object(m.group("class"))
            # Může mít více instancí
            for inst in _split_names(m.group("insts")):
                ensure_link(get_or_create_object(inst), cls, "instantiation")
            continue

        # === States - výčet možných stavů objektu ===
        # Příklad: "Order can be Pending, Confirmed or Delivered."
        m = RE_STATES.match(line)
        if m:
            obj = get_or_create_object(m.group("obj"))
            # Vytvoří všechny uvedené stavy jako potomky objektu
            for st in _split_states(m.group("states")):
                get_or_create_state(obj, st)
            continue

        # === Simple "is a" - jednoduchá generalizace ===
        # Příklad: "Car is a Vehicle." nebo "Abs is a Braking System."
        # Poznámka: Link vytváříme jako sub → sup (protože generátor prohodí src↔dst pro strukturální vazby)
        # Poznámka: Rozlišujeme generalizaci od definice atributů - generalizace má druhý název (super) začínající velkým písmenem
        m = RE_IS_A.match(line)
        if m:
            super_name = m.group("super").strip()
            # Kontrola, zda to není definice atributů (pak by super_name bylo malými písmeny: physical, informatical, systemic, environmental)
            # Pokud super_name začíná velkým písmenem, je to generalizace
            if super_name and super_name[0].isupper():
                sub = get_or_create_object(m.group("sub"))
                sup = get_or_create_object(super_name)
                ensure_link(sub, sup, "generalization")
            continue

        # === Simple "is an instance of" - jednoduchá instantiace ===
        # Příklad: "John is an instance of Person."
        m = RE_INSTANCE.match(line)
        if m:
            inst = get_or_create_object(m.group("inst"))
            klass = get_or_create_object(m.group("class"))
            ensure_link(klass, inst, "instantiation")
            continue

        # === State change - proces mění objekt z jednoho stavu do druhého ===
        # Příklad: "Processing changes Order from Pending to Confirmed."
        m = RE_CHANGES.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            obj = get_or_create_object(m.group("obj"))
            # Vytvoří oba stavy (pokud neexistují)
            s_from = get_or_create_state(obj, m.group("from"))
            s_to = get_or_create_state(obj, m.group("to"))
            # Vstupní stav → proces, proces → výstupní stav
            ensure_link(s_from, p, "consumption")
            ensure_link(p, s_to, "result")
            continue

        # === Can be - alternativní syntaxe pro stavy ===
        # Příklad: "Light can be On or Off."
        m = RE_CANBE.match(line)
        if m:
            obj = get_or_create_object(m.group("obj"))
            # Vytvoří všechny uvedené stavy jako potomky objektu
            for st in _split_states(m.group("states")):
                get_or_create_state(obj, st)
            continue

        # Pokud žádný regex nerozpoznal větu, přidá ji do seznamu ignorovaných
        ignored.append(line)

    # Vrátí seznam nerozpoznaných řádků pro informaci uživateli
    return ignored