from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Tuple
from graphics.link import LinkItem
from graphics.nodes import ObjectItem, ProcessItem

def _opl_join(names: List[str]) -> str:
    if not names: return ""
    names = list(dict.fromkeys(names))
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]

def preview_opl(scene) -> str:
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
        "whole_parts": defaultdict(list),
        "characterized": defaultdict(list),
        "exhibits": defaultdict(list),
        "generalizes": defaultdict(list),
        "classifies": defaultdict(list),
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
            if lt in ("aggregation","participation"):
                struct_b["whole_parts"][d_label].append(s_label)
            elif lt == "characterization":
                struct_b["characterized"][s_label].append(d_label)
            elif lt == "exhibition":
                struct_b["exhibits"][s_label].append(d_label)
            elif lt in ("specialization","generalization"):
                struct_b["generalizes"][d_label].append(s_label)
            elif lt in ("instantiation","classification"):
                struct_b["classifies"][d_label].append(s_label)

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

    for whole, parts in struct_b["whole_parts"].items():
        if parts: lines.append(f"{whole} is composed of {_opl_join(sorted(parts))}.")
    for obj, attrs in struct_b["characterized"].items():
        if attrs: lines.append(f"{obj} is characterized by {_opl_join(sorted(attrs))}.")
    for obj, attrs in struct_b["exhibits"].items():
        if attrs: lines.append(f"{obj} exhibits {_opl_join(sorted(attrs))}.")
    for sup, subs in struct_b["generalizes"].items():
        if subs: lines.append(f"{sup} generalizes {_opl_join(sorted(subs))}.")
    for cls, insts in struct_b["classifies"].items():
        if insts: lines.append(f"{cls} has instances {_opl_join(sorted(insts))}.")

    return "\n".join(lines) if lines else "-- OPL preview has no content yet --"