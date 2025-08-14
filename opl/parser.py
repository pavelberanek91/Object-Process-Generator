from __future__ import annotations
from typing import Dict, List
from PySide6.QtCore import QPointF, QRectF
from graphics.nodes import ObjectItem, ProcessItem
from graphics.link import LinkItem
from constants import NODE_W, NODE_H
from opl.regexes import *

def _norm(name: str) -> str:
    return name.strip().strip('"')

def _split_names(s: str) -> List[str]:
    import re
    s = s.strip().strip(".")
    s = re.sub(r"\s+and\s+", ", ", s)
    parts = [p.strip().strip('"') for p in s.split(",")]
    return [p for p in parts if p]

def build_from_opl(app, text: str):
    """Postaví/rozšíří diagram v 'app.scene' na základě OPL vět v textu."""
    scene = app.scene
    # mapy existujícího stavu
    by_label: Dict[str, object] = {}
    kind_of: Dict[str, str] = {}
    for it in scene.items():
        if isinstance(it, (ObjectItem, ProcessItem)):
            by_label[it.label] = it
            kind_of[it.label] = it.kind

    items_rect = scene.itemsBoundingRect() if scene.items() else QRectF(-200,-150,400,300)
    base_x = items_rect.right() + 150
    proc_i = 0; obj_i = 0

    def next_proc_pos():
        nonlocal proc_i
        p = app.snap(QPointF(base_x + proc_i * 200, -150)); proc_i += 1; return p

    def next_obj_pos():
        nonlocal obj_i
        p = app.snap(QPointF(base_x + obj_i * 200,  130)); obj_i += 1; return p

    def get_or_create_process(name: str):
        name = _norm(name)
        it = by_label.get(name)
        if it and isinstance(it, ProcessItem): return it
        if it and isinstance(it, ObjectItem):  return it
        item = ProcessItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H), name)
        item.setPos(next_proc_pos()); scene.addItem(item)
        by_label[name] = item; kind_of[name] = "process"
        return item

    def get_or_create_object(name: str):
        name = _norm(name)
        it = by_label.get(name)
        if it and isinstance(it, ObjectItem):   return it
        if it and isinstance(it, ProcessItem):  return it
        item = ObjectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H), name)
        item.setPos(next_obj_pos()); scene.addItem(item)
        by_label[name] = item; kind_of[name] = "object"
        return item

    def ensure_link(src, dst, lt: str, label: str=""):
        for it in scene.items():
            if isinstance(it, LinkItem) and it.src is src and it.dst is dst and it.link_type == lt:
                return it
        ln = LinkItem(src, dst, lt, label); scene.addItem(ln); return ln

    ignored: List[str] = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue

        m = RE_CONSUMES.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            for o in _split_names(m.group("objs")):
                ensure_link(get_or_create_object(o), p, "consumption")
            continue

        m = RE_INPUTS.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            for o in _split_names(m.group("objs")):
                ensure_link(get_or_create_object(o), p, "input")
            continue

        m = RE_YIELDS.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            for o in _split_names(m.group("objs")):
                ensure_link(p, get_or_create_object(o), "output")
            continue

        m = RE_HANDLES.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            for a in _split_names(m.group("agents")):
                ensure_link(get_or_create_object(a), p, "agent")
            continue

        m = RE_REQUIRES.match(line)
        if m:
            p = get_or_create_process(m.group("p"))
            for ins in _split_names(m.group("objs")):
                ensure_link(get_or_create_object(ins), p, "instrument")
            continue

        m = RE_AFFECTS.match(line)
        if m:
            x = _norm(m.group("x")); y = _norm(m.group("y"))
            if kind_of.get(x) == "process" or kind_of.get(y) == "object":
                ensure_link(get_or_create_process(x), get_or_create_object(y), "effect")
            elif kind_of.get(x) == "object" or kind_of.get(y) == "process":
                ensure_link(get_or_create_object(x), get_or_create_process(y), "effect")
            else:
                ensure_link(get_or_create_process(x), get_or_create_object(y), "effect")
            continue

        m = RE_COMPOSED.match(line)
        if m:
            whole = get_or_create_object(m.group("whole"))
            for part in _split_names(m.group("parts")):
                ensure_link(get_or_create_object(part), whole, "aggregation")
            continue

        m = RE_CHARAC.match(line)
        if m:
            obj = get_or_create_object(m.group("obj"))
            for attr in _split_names(m.group("attrs")):
                ensure_link(obj, get_or_create_object(attr), "characterization")
            continue

        m = RE_EXHIBITS.match(line)
        if m:
            obj = get_or_create_object(m.group("obj"))
            for attr in _split_names(m.group("attrs")):
                ensure_link(obj, get_or_create_object(attr), "exhibition")
            continue

        m = RE_GENER.match(line)
        if m:
            sup = get_or_create_object(m.group("super"))
            for sub in _split_names(m.group("subs")):
                ensure_link(get_or_create_object(sub), sup, "generalization")
            continue

        m = RE_INSTANCES.match(line)
        if m:
            cls = get_or_create_object(m.group("class"))
            for inst in _split_names(m.group("insts")):
                ensure_link(get_or_create_object(inst), cls, "instantiation")
            continue

        ignored.append(line)

    return ignored