"""Převodník OPM diagramu na Petriho síť."""
from __future__ import annotations
from typing import Dict, Set, Optional, Tuple
from simulation.petri_net import PetriNet, Place, Transition, Arc
from graphics.nodes import ObjectItem, ProcessItem, StateItem


def build_petri_net_from_scene(scene) -> PetriNet:
    """Vytvoří Petriho síť z OPM diagramu ve scéně.
    
    Args:
        scene: QGraphicsScene obsahující OPM diagram
        
    Returns:
        PetriNet instance reprezentující diagram
    """
    net = PetriNet()
    
    # Mapování objektů a jejich stavů
    objects: Dict[str, ObjectItem] = {}
    states_by_object: Dict[str, Dict[str, StateItem]] = {}  # object_id -> {state_label -> StateItem}
    processes: Dict[str, ProcessItem] = {}
    
    # Projdi všechny uzly ve scéně
    # POZNÁMKA: scene.items() vrací všechny items včetně child items
    print(f"[Converter] Scanning scene with {len(scene.items())} items")
    item_count = 0
    for item in scene.items():
        if isinstance(item, ObjectItem):
            if not hasattr(item, 'node_id') or not item.node_id:
                print(f"[Converter] WARNING: ObjectItem '{item.label}' has no node_id")
                continue
            objects[item.node_id] = item
            item_count += 1
            # Inicializuj prázdný slovník pro stavy, pokud ještě neexistuje
            if item.node_id not in states_by_object:
                states_by_object[item.node_id] = {}
            # Najdi všechny child stavy tohoto objektu
            for child in item.childItems():
                if isinstance(child, StateItem):
                    states_by_object[item.node_id][child.label] = child
                    print(f"[Converter] Found state '{child.label}' for object '{item.label}'")
        elif isinstance(item, StateItem):
            # StateItem může být také top-level item (např. po undo/redo)
            parent = item.parentItem()
            if parent and isinstance(parent, ObjectItem):
                if not hasattr(parent, 'node_id') or not parent.node_id:
                    print(f"[Converter] WARNING: Parent ObjectItem has no node_id")
                    continue
                obj_id = parent.node_id
                if obj_id not in states_by_object:
                    states_by_object[obj_id] = {}
                states_by_object[obj_id][item.label] = item
        elif isinstance(item, ProcessItem):
            if not hasattr(item, 'node_id') or not item.node_id:
                print(f"[Converter] WARNING: ProcessItem '{item.label}' has no node_id")
                continue
            processes[item.node_id] = item
            item_count += 1
    
    print(f"[Converter] Found {len(objects)} objects, {len(processes)} processes, {sum(len(states) for states in states_by_object.values())} states")
    
    # Vytvoř místa pro každý objekt (místo pro každý stav nebo obecné místo)
    place_map: Dict[str, str] = {}  # (object_id, state_label?) -> place_id
    
    for obj_id, obj in objects.items():
        states = states_by_object.get(obj_id, {})
        
        if states:
            # Objekt má stavy - vytvoř místo pro každý stav
            for state_label, state_item in states.items():
                place_id = f"place_{obj_id}_{state_label}"
                place = Place(
                    id=place_id,
                    label=f"{obj.label} at state {state_label}",
                    object_id=obj_id,
                    state_label=state_label
                )
                net.add_place(place)
                place_map[(obj_id, state_label)] = place_id
        else:
            # Objekt bez stavů - vytvoř jedno obecné místo
            place_id = f"place_{obj_id}"
            place = Place(
                id=place_id,
                label=obj.label,
                object_id=obj_id,
                state_label=None
            )
            net.add_place(place)
            place_map[(obj_id, None)] = place_id
            print(f"[Converter] Created place for object without states: {obj.label} ({place_id})")
    
    # Vytvoř přechody pro každý proces
    for proc_id, proc in processes.items():
        transition_id = f"transition_{proc_id}"
        transition = Transition(
            id=transition_id,
            label=proc.label,
            process_id=proc_id
        )
        net.add_transition(transition)
        print(f"[Converter] Created transition: {proc.label} ({transition_id})")
    
    # Projdi všechny linky a vytvoř oblouky
    for item in scene.items():
        from graphics.link import LinkItem
        if not isinstance(item, LinkItem):
            continue
            
        link = item
        src = link.src
        dst = link.dst
        link_type = link.link_type
        
        # Zjisti, zda je zdroj nebo cíl proces
        src_process = None
        dst_process = None
        
        if isinstance(src, ProcessItem):
            src_process = src
        if isinstance(dst, ProcessItem):
            dst_process = dst
        
        # Procedurální vazby
        if link_type == "consumption":
            # Consumption může být buď obj→proc nebo proc→obj
            # V OPM: "P consumes A" vytváří link obj→proc
            if isinstance(src, (ObjectItem, StateItem)) and dst_process:
                # Objekt/stav k procesu: proces spotřebovává objekt
                obj, state_label = _get_object_and_state(src)
                if obj:
                    place_id = _find_place_id(obj.node_id, state_label, place_map)
                    if place_id:
                        arc = Arc(
                            place_id=place_id,
                            transition_id=f"transition_{dst_process.node_id}",
                            arc_type="input"
                        )
                        net.add_arc(arc)
                        print(f"[Converter] Added consumption arc: {obj.label} ({place_id}) → {dst_process.label}")
            elif src_process and isinstance(dst, (ObjectItem, StateItem)):
                # Proces k objektu/stavu: proces spotřebovává objekt (alternativní směr)
                obj, state_label = _get_object_and_state(dst)
                if obj:
                    place_id = _find_place_id(obj.node_id, state_label, place_map)
                    if place_id:
                        arc = Arc(
                            place_id=place_id,
                            transition_id=f"transition_{src_process.node_id}",
                            arc_type="input"
                        )
                        net.add_arc(arc)
                        
        elif link_type == "result":
            # Result může být buď proc→obj nebo obj→proc
            # V OPM: "P yields A" vytváří link proc→obj
            if src_process and isinstance(dst, (ObjectItem, StateItem)):
                # Proces k objektu/stavu: proces vytváří objekt
                obj, state_label = _get_object_and_state(dst)
                if obj:
                    place_id = _find_place_id(obj.node_id, state_label, place_map)
                    if place_id:
                        arc = Arc(
                            place_id=place_id,
                            transition_id=f"transition_{src_process.node_id}",
                            arc_type="output"
                        )
                        net.add_arc(arc)
                        print(f"[Converter] Added result arc: {src_process.label} → {obj.label} ({place_id})")
            elif isinstance(src, (ObjectItem, StateItem)) and dst_process:
                # Objekt/stav k procesu: proces vytváří objekt (alternativní směr)
                obj, state_label = _get_object_and_state(src)
                if obj:
                    place_id = _find_place_id(obj.node_id, state_label, place_map)
                    if place_id:
                        arc = Arc(
                            place_id=place_id,
                            transition_id=f"transition_{dst_process.node_id}",
                            arc_type="output"
                        )
                        net.add_arc(arc)
                        
        elif link_type == "effect":
            # Proces ovlivňuje objekt (bidirekcionální - vytvoříme test oblouk)
            if src_process and isinstance(dst, (ObjectItem, StateItem)):
                obj, state_label = _get_object_and_state(dst)
                if obj:
                    place_id = _find_place_id(obj.node_id, state_label, place_map)
                    if place_id:
                        # Effect může být test (vyžaduje token) nebo output (vytváří token)
                        # Pro jednoduchost použijeme test oblouk
                        arc = Arc(
                            place_id=place_id,
                            transition_id=f"transition_{src_process.node_id}",
                            arc_type="test"
                        )
                        net.add_arc(arc)
            elif isinstance(src, (ObjectItem, StateItem)) and dst_process:
                obj, state_label = _get_object_and_state(src)
                if obj:
                    place_id = _find_place_id(obj.node_id, state_label, place_map)
                    if place_id:
                        arc = Arc(
                            place_id=place_id,
                            transition_id=f"transition_{dst_process.node_id}",
                            arc_type="test"
                        )
                        net.add_arc(arc)
                        
        elif link_type == "agent":
            # Agent řídí proces (test oblouk)
            if isinstance(src, ObjectItem) and dst_process:
                place_id = _find_place_id(src.node_id, None, place_map)
                if place_id:
                    arc = Arc(
                        place_id=place_id,
                        transition_id=f"transition_{dst_process.node_id}",
                        arc_type="test"
                    )
                    net.add_arc(arc)
                    
        elif link_type == "instrument":
            # Proces vyžaduje nástroj (test oblouk)
            if dst_process and isinstance(src, ObjectItem):
                place_id = _find_place_id(src.node_id, None, place_map)
                if place_id:
                    arc = Arc(
                        place_id=place_id,
                        transition_id=f"transition_{dst_process.node_id}",
                        arc_type="test"
                    )
                    net.add_arc(arc)
    
    # Zpracuj "changes from...to..." vazby
    # "Changes" vazby se vytváří jako pár: consumption na stav A a result na stav B stejného objektu
    # Musíme najít tyto páry a zajistit, že jsou správně zpracovány
    # (Poznámka: V OPL parseru se "changes" vytváří jako dva linky - consumption a result)
    # Pro jednoduchost necháme současnou logiku - consumption a result jsou již správně zpracovány výše
    
    print(f"[Converter] Petri net created: {len(net.places)} places, {len(net.transitions)} transitions, {len(net.arcs)} arcs")
    if len(net.places) == 0:
        print("[Converter] WARNING: No places created! Check if objects are in the scene with proper node_id.")
    if len(net.transitions) == 0:
        print("[Converter] WARNING: No transitions created! Check if processes are in the scene with proper node_id.")
    
    return net


def _get_object_and_state(item) -> Tuple[Optional[ObjectItem], Optional[str]]:
    """Získá objekt a stav z itemu (stav nebo objekt)."""
    if isinstance(item, StateItem):
        parent = item.parentItem()
        if parent and isinstance(parent, ObjectItem):
            return parent, item.label
    elif isinstance(item, ObjectItem):
        return item, None
    return None, None


def _find_place_id(object_id: str, state_label: Optional[str], place_map: Dict) -> Optional[str]:
    """Najde ID místa pro daný objekt a stav."""
    key = (object_id, state_label)
    return place_map.get(key)

