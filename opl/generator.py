"""Generátor OPL vět z diagramu - převádí vizuální diagram zpět na textové OPL."""
from collections import defaultdict
from typing import Dict, List, Tuple
from graphics.link import LinkItem
from graphics.nodes import ObjectItem, ProcessItem, StateItem


def _opl_join(names: List[str]) -> str:
    """
    Spojí seznam názvů do OPL-friendly textu: 'A, B and C'.
    
    Používá se pro objekty/procesy (spojují se pomocí "and").
    Odstraní duplicity při zachování pořadí.
    """
    if not names: 
        return ""
    names = list(dict.fromkeys(names))  # Deduplikace
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _opl_join_states(names: List[str]) -> str:
    """
    Spojí seznam stavů do OPL-friendly textu: 'A, B or C'.
    
    Používá se pro stavy (spojují se pomocí "or").
    """
    if not names: 
        return ""
    names = list(dict.fromkeys(names))
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


def preview_opl(scene) -> str:
    """
    Generuje OPL věty ze scény (reverse operation parseru).
    
    Projde všechny uzly a vazby v diagramu a vytvoří odpovídající OPL věty.
    
    Args:
        scene: QGraphicsScene obsahující diagram
    
    Returns:
        Text s OPL větami (jedna věta na řádek)
    """
    # === Inicializace mapování pro rychlé vyhledávání ===
    nodes: Dict[str, Tuple[str, str]] = {}       # node_id → (kind, label)
    id_to_parent: Dict[str, str] = {}            # state_id → parent_object_id
    proc_labels: Dict[str, str] = {}             # process_id → label (pro rychlý přístup)

    for it in scene.items():
        if isinstance(it, (ObjectItem, ProcessItem, StateItem)):
            nodes[it.node_id] = (it.kind, it.label)
            if isinstance(it, ProcessItem):
                proc_labels[it.node_id] = it.label
            if isinstance(it, StateItem):
                parent = it.parentItem()
                if parent and hasattr(parent, "node_id"):
                    id_to_parent[it.node_id] = parent.node_id

    # === Pomocná funkce pro formátování názvu entity ===
    def ent(nid: str) -> str:
        """
        Vrátí OPL-friendly název entity.
        Pro stavy: "Parent at state State", pro ostatní jen label.
        """
        kind, label = nodes.get(nid, ("?", "?"))
        if kind == "state" and nid in id_to_parent:
            parent_label = nodes.get(id_to_parent[nid], ("?", "?"))[1]
            return f"{parent_label} at state {label}"
        return label

    # === Inicializace kontejnerů pro sběr vazeb ===
    # Procedurální vazby - seskupené podle procesů
    buckets = defaultdict(lambda: {
        "consumes": [], "inputs": [], "yields": [], "affects": [], "agents": [], "instruments": [],
    })
    # Speciální: páry input-output stavů (pro "changes from...to...")
    proc_state_links: Dict[str, Dict[str, Dict[str, str]]] = defaultdict(lambda: defaultdict(dict))
    # Strukturální vazby - seskupené podle typu
    struct_b = {
        "aggregation": defaultdict(list),    # Celek → části
        "exhibition": defaultdict(list),     # Objekt → vlastnosti
        "generalization": defaultdict(list), # Rodič → potomci
        "instantiation": defaultdict(list),  # Třída → instance
    }

    # === Procházení všech vazeb a jejich kategorizace ===
    for it in scene.items():
        if not isinstance(it, LinkItem): 
            continue
        # Získání ID a metadat zdrojového a cílového uzlu
        s = getattr(it.src, "node_id", "")
        d = getattr(it.dst, "node_id", "")
        s_kind, s_label = nodes.get(s, ("?", "?"))
        d_kind, d_label = nodes.get(d, ("?", "?"))
        lt = it.link_type.lower()

        # === Případ: OBJEKT/STAV → PROCES (procedurální vazby) ===
        if s_kind in {"object", "state"} and d_kind == "process":
            if lt == "consumption":   
                buckets[d]["consumes"].append(ent(s))
            elif lt == "agent":       
                buckets[d]["agents"].append(ent(s))
            elif lt == "instrument":  
                buckets[d]["instruments"].append(ent(s))
            elif lt == "effect":      
                buckets[d]["affects"].append(ent(s))
            elif lt == "input":       
                buckets[d]["inputs"].append(ent(s))
                # pokud jde o stav -> uložíme jako input state
                if s_kind == "state" and s in id_to_parent:
                    obj_label = nodes[id_to_parent[s]][1]
                    proc_state_links[d][obj_label]["in"] = s_label

        # === Případ: PROCES → OBJEKT/STAV (procedurální vazby opačným směrem) ===
        elif s_kind == "process" and d_kind in {"object", "state"}:
            if lt == "effect":           
                buckets[s]["affects"].append(ent(d))
            elif lt in ("result", "output"): 
                if d_kind == "object":
                    # celý objekt -> yield
                    buckets[s]["yields"].append(ent(d))
                elif d_kind == "state" and d in id_to_parent:
                    # stav -> jen pro změnový pár, ne yield
                    obj_label = nodes[id_to_parent[d]][1]
                    proc_state_links[s][obj_label]["out"] = d_label
            
        elif s_kind in ("object","process") and d_kind in ("object","process"):
            # Všechny strukturální vazby: marker ikony je vždy tam, kde začíná vazba (src)
            # Ale v OPL sémantice marker má být u specifického uzlu (celek, rodič, třída)
            # Uživatel při kreslení klikne od "běžného" uzlu k "významnému" uzlu (s markerem)
            # Proto musíme prohodit src↔dst pro všechny strukturální vazby
            struct_b[lt][ent(d)].append(ent(s))

    # seznam vygenerovanych OPL vet
    lines: List[str] = []

    # 1) Objekty a jejich stavy
    object_states: Dict[str, List[str]] = defaultdict(list)
    for it in scene.items():
        if isinstance(it, StateItem):
            parent = it.parentItem()
            if parent and isinstance(parent, ObjectItem):
                object_states[parent.label].append(it.label)

    for obj, states in object_states.items():
        if states:
            if len(states) == 1:
                lines.append(f"{obj} is {_opl_join_states(sorted(states))}.")
            else:
                lines.append(f"{obj} can be {_opl_join_states(sorted(states))}.")

    # 2) Procesní vazby
    for pid, b in buckets.items():
        pname = proc_labels.get(pid)
        if not pname: 
            continue

        # input/output pairs
        if pid in proc_state_links:
            for obj, pair in proc_state_links[pid].items():
                if "in" in pair and "out" in pair:
                    lines.append(f"{pname} changes {obj} from {pair['in']} to {pair['out']}.")

        if b["consumes"]:    
            lines.append(f"{pname} consumes {_opl_join(b['consumes'])}.")
        if b["inputs"]:      
            lines.append(f"{pname} takes {_opl_join(b['inputs'])} as input.")
        if b["yields"]:      
            lines.append(f"{pname} yields {_opl_join(b['yields'])}.")
        if b["affects"]:     
            lines.append(f"{pname} affects {_opl_join(b['affects'])}.")
        if b["agents"]:      
            lines.append(f"{_opl_join(b['agents'])} handles {pname}.")
        if b["instruments"]: 
            lines.append(f"{pname} requires {_opl_join(b['instruments'])}.")

    # 3) strukturalni vazby
    for whole, parts in struct_b["aggregation"].items():
        if parts: 
            lines.append(f"{whole} consists of {_opl_join(sorted(parts))}.")
    for obj, attrs in struct_b["exhibition"].items():
        if attrs: 
            lines.append(f"{obj} exhibits {_opl_join(sorted(attrs))}.")
    for sup, subs in struct_b["generalization"].items():
        if subs: 
            lines.append(f"{_opl_join(sorted(subs))} {'is a' if len(subs) == 1 else 'are'} {sup}{'s' if len(subs) > 1 else ''}.")
    for cls, insts in struct_b["instantiation"].items():
        if insts: 
            lines.append(f"{_opl_join(sorted(insts))} {'is an' if len(insts) == 1 else 'are'} instance{'s' if len(insts) > 1 else ''} of {cls}.")

    return "\n".join(lines) if lines else "-- OPL preview has no content yet --"