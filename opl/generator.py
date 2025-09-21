from collections import defaultdict
from typing import Dict, List, Tuple
from graphics.link import LinkItem
from graphics.nodes import ObjectItem, ProcessItem

def _opl_join(names: List[str]) -> str:
    """Spojí seznam názvů do OPL-friendly textu: 'A, B and C' (zachová pořadí, odstraní duplicity)."""
    if not names: return ""
    names = list(dict.fromkeys(names))
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]

def preview_opl(scene) -> str:
    """
    Projde položky ve scéně, sesbírá informace o uzlech a linkách a vrátí OPL věty jako text 
    (jedna věta na řádek).
    """
    nodes: Dict[str, Tuple[str, str]] = {}
    proc_labels: Dict[str, str] = {}
    for it in scene.items():
        if isinstance(it, (ObjectItem, ProcessItem)):
            nodes[it.node_id] = (it.kind, it.label)
            if isinstance(it, ProcessItem):
                proc_labels[it.node_id] = it.label

    buckets = defaultdict(lambda: {
        "consumes": [], "inputs": [], "yields": [], "affects": [], "agents": [], "instruments": [],
    })
    struct_b = {
        "aggregation": defaultdict(list),
        "exhibition": defaultdict(list),
        "generalization": defaultdict(list),
        "instantiation": defaultdict(list),
    }

    for it in scene.items():
        if not isinstance(it, LinkItem): continue
        s = getattr(it.src, "node_id", ""); d = getattr(it.dst, "node_id", "")
        s_kind, s_label = nodes.get(s, ("?", "?")); d_kind, d_label = nodes.get(d, ("?", "?"))
        lt = it.link_type.lower()

        if s_kind == "object" and d_kind == "process":
            if lt == "consumption":   buckets[d]["consumes"].append(s_label)
            elif lt == "input":       buckets[d]["inputs"].append(s_label)
            elif lt == "agent":       buckets[d]["agents"].append(s_label)
            elif lt == "instrument":  buckets[d]["instruments"].append(s_label)
            elif lt == "effect":      buckets[d]["affects"].append(s_label)

        elif s_kind == "process" and d_kind == "object":
            if lt in ("result", "output"): buckets[s]["yields"].append(d_label)
            elif lt == "effect":           buckets[s]["affects"].append(d_label)

        elif s_kind in ("object","process") and d_kind in ("object","process"):
            struct_b[lt][s_label].append(d_label)

    lines: List[str] = []
    for pid, b in buckets.items():
        pname = proc_labels.get(pid)
        if not pname: continue
        if b["consumes"]:    lines.append(f"{pname} consumes {_opl_join(b['consumes'])}.")
        if b["inputs"]:      lines.append(f"{pname} takes {_opl_join(b['inputs'])} as input.")
        if b["yields"]:      lines.append(f"{pname} yields {_opl_join(b['yields'])}.")
        if b["affects"]:     lines.append(f"{pname} affects {_opl_join(b['affects'])}.")
        if b["agents"]:      lines.append(f"{_opl_join(b['agents'])} handle {pname}.")
        if b["instruments"]: lines.append(f"{pname} requires {_opl_join(b['instruments'])}.")

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