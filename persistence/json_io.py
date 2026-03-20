"""Modul pro import/export diagramů do/z JSON formátu (persistence).

Zajišťuje ukládání a načítání kompletního stavu diagramu včetně pozic, 
velikostí uzlů, typů vazeb a všech metadat.
"""
import json
import os
import re
from dataclasses import asdict
from typing import Dict, Any, List

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QFileDialog, QMessageBox, QGraphicsItem
from graphics.nodes import ObjectItem, ProcessItem, StateItem
from graphics.link import LinkItem
from constants import NODE_W, NODE_H, STATE_W, STATE_H, LINK_TYPES, PROCEDURAL_TYPES, STRUCTURAL_TYPES, GRID_SIZE
from utils.ids import next_id
from opd.models import DiagramNode, DiagramLink


def safe_base_filename(title: str | None = None) -> str:
    """
    Vytvoří bezpečný název souboru z názvu tabu (odstraní zakázané znaky).
    
    Args:
        title: Název tabu/diagramu
    
    Returns:
        Bezpečný název souboru (bez přípony)
    """
    base = (title or "OPD").strip()
    # Odstraní emoji prefixy (ikonky domáčku a zoomu)
    base = base.replace("🔍 ", "").replace("🏠 ", "").strip()
    # Nahradí zakázané znaky podtržítkem
    base = re.sub(r'[\\/*?:"<>|]+', "_", base)
    base = re.sub(r"\s+", "_", base)  # Více mezer → jedno podtržítko
    return base or "Canvas"
    

def scene_to_dict(scene) -> Dict[str, Any]:
    """
    Převede scénu s diagramem na slovník (pro JSON export).
    
    Args:
        scene: QGraphicsScene obsahující diagram
    
    Returns:
        Slovník s klíči "nodes", "links" a "meta"
    """
    nodes: List[DiagramNode] = []  # Seznam uzlů pro export
    links: List[DiagramLink] = []  # Seznam vazeb pro export
    
    # === Sběr uzlů (objekty, procesy, stavy) ===
    for it in scene.items():
        if isinstance(it, (ObjectItem, ProcessItem)):
            r_scene = it.mapRectToScene(it.rect())
            nodes.append(DiagramNode(
                id=it.node_id,
                kind=it.kind,
                label=it.label,
                x=r_scene.center().x(),
                y=r_scene.center().y(),
                w=r_scene.width(),
                h=r_scene.height(),
                parent_process_id=getattr(it, 'parent_process_id', None),
                essence=it.essence,
                affiliation=it.affiliation
            ))
            if isinstance(it, ObjectItem):
                for ch in it.childItems():
                    if isinstance(ch, StateItem):
                        sr = ch.mapRectToScene(ch.rect())
                        nodes.append(DiagramNode(
                            id=ch.node_id,
                            kind="state",
                            label=ch.label,
                            x=sr.center().x(),
                            y=sr.center().y(),
                            w=sr.width(),
                            h=sr.height(),
                            parent_id=it.node_id
                        ))
                        
    for it in scene.items():
        if isinstance(it, LinkItem):
            links.append(DiagramLink(
                id=next_id("link"),
                src=getattr(it.src, "node_id", ""),
                dst=getattr(it.dst, "node_id", ""),
                link_type=it.link_type,
                label=it.label,
                type_dx=getattr(it, "_type_offset", QPointF(6,-6)).x(),
                type_dy=getattr(it, "_type_offset", QPointF(6,-6)).y(),
                label_dx=(getattr(it, "_label_offset", QPointF(6,12)).x()
                          if getattr(it, "ti_label", None) else 6.0),
                label_dy=(getattr(it, "_label_offset", QPointF(6,12)).y()
                          if getattr(it, "ti_label", None) else 12.0),
                card_src=it.card_src if hasattr(it, "card_src") else "",
                card_dst=it.card_dst if hasattr(it, "card_dst") else "",
            ))
            
    return {
        "nodes": [asdict(n) for n in nodes],
        "links": [asdict(l) for l in links],
        "meta": {"format": "opm-mvp-json", "version": 1}
    }
    

def dict_to_scene(scene, data: Dict[str, Any], allowed_link) -> None:
    """
    Načte slovník (z JSON) do scény.
    
    Args:
        scene: Cílová QGraphicsScene
        data: Slovník s klíči "nodes" a "links"
        allowed_link: Callback funkce pro validaci vazeb
    """
    scene.clear()  # Vyčistí scénu před načtením
    id_to_item: Dict[str, QGraphicsItem] = {}  # Mapování ID → item pro propojení vazeb
    
    for n in data.get("nodes", []):
        kind = n["kind"]
        pos = QPointF(n["x"], n["y"])
        if kind == "object":
            it = ObjectItem(
                QRectF(-n["w"]/2, -n["h"]/2, n["w"], n["h"]), 
                n["label"],
                essence=n.get("essence", "informatical"),
                affiliation=n.get("affiliation", "systemic")
            )
            it.node_id = n["id"]
            it.parent_process_id = n.get("parent_process_id")
            it.setPos(pos)
            scene.addItem(it)
            id_to_item[n["id"]] = it
            
    for n in data.get("nodes", []):
        if n["kind"] == "process":
            it = ProcessItem(
                QRectF(-n["w"]/2, -n["h"]/2, n["w"], n["h"]), 
                n["label"],
                essence=n.get("essence", "informatical"),
                affiliation=n.get("affiliation", "systemic")
            )
            it.node_id = n["id"]
            it.parent_process_id = n.get("parent_process_id")
            it.setPos(QPointF(n["x"], n["y"]))
            scene.addItem(it); id_to_item[n["id"]] = it
            
    for n in data.get("nodes", []):
        if n["kind"] == "state" and n.get("parent_id") in id_to_item:
            parent = id_to_item[n["parent_id"]]
            local_center = parent.mapFromScene(QPointF(n["x"], n["y"]))
            rect = QRectF(local_center.x()-n["w"]/2, local_center.y()-n["h"]/2, n["w"], n["h"])
            it = StateItem(parent, rect, n["label"])
            it.node_id = n["id"]
            scene.addItem(it)
            id_to_item[n["id"]] = it

    invalid = 0
    for l in data.get("links", []):
        src = id_to_item.get(l["src"])
        dst = id_to_item.get(l["dst"])
        if src and dst:
            lt = l.get("link_type", "consumption")
            ok, msg = allowed_link(src, dst, lt)
            if not ok:
                invalid += 1
                continue
            li = LinkItem(src, dst, lt, l.get("label", ""))
            scene.addItem(li)    
            li._type_offset  = QPointF(l.get("type_dx", 6.0),  l.get("type_dy", -6.0))
            li._label_offset = QPointF(l.get("label_dx", 6.0), l.get("label_dy", 12.0))
            li.set_card_src(l.get("card_src", ""))
            li.set_card_dst(l.get("card_dst", ""))
            li.update_path()
            
    if invalid:
        QMessageBox.warning(None, "Některé vazby přeskočeny",
                            f"{invalid} neplatných vazeb bylo při načítání přeskočeno.")
        
        
def save_scene_as_json(scene, title: str | None = None, main_window=None):
    """
    Uloží diagram do JSON souboru (s dialogem pro výběr cesty).
    
    Pokud je poskytnut main_window, uloží celý globální datový model včetně
    všech zoom-in hierarchií. Jinak uloží pouze aktuální scénu.
    
    Args:
        scene: Scéna k uložení (použije se pro zpětnou kompatibilitu)
        title: Název tabu (použije se jako výchozí název souboru)
        main_window: MainWindow instance pro přístup k _global_diagram_data
    """
    base = safe_base_filename(title)
    path, _ = QFileDialog.getSaveFileName(None, "Save OPD (JSON)", f"{base}.json", "JSON (*.json)")
    if not path: 
        return
    
    # Pokud máme main_window, uložíme celý globální model (včetně hierarchií)
    if main_window and hasattr(main_window, '_global_diagram_data'):
        # Nejdřív synchronizujme aktuální scénu do globálního modelu
        current_view = None
        parent_process_id = None
        for i in range(main_window.tabs.count()):
            view = main_window.tabs.widget(i)
            if view.scene() == scene:
                current_view = view
                parent_process_id = getattr(view, 'zoomed_process_id', None)
                break
        
        if current_view:
            main_window.sync_scene_to_global_model(scene, parent_process_id)
        
        # Uložme celý globální datový model
        data_to_save = {
            "nodes": main_window._global_diagram_data.get("nodes", []),
            "links": main_window._global_diagram_data.get("links", []),
            "meta": {
                **main_window._global_diagram_data.get("meta", {}),
                "format": "opm-mvp-json-hierarchy",
                "version": 2  # Verze 2 podporuje hierarchie
            }
        }
    else:
        # Zpětná kompatibilita - uložíme jen aktuální scénu
        data_to_save = scene_to_dict(scene)
        data_to_save["meta"] = data_to_save.get("meta", {})
        data_to_save["meta"]["format"] = "opm-mvp-json"
        data_to_save["meta"]["version"] = 1
    
    # Uložení do souboru s UTF-8 encoding a odsazením pro čitelnost
    with open(path, "w", encoding="utf-8") as f: 
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)


def load_scene_from_json(scene, allowed_link, new_canvas_callback=None, new_tab: bool = False, main_window=None):
    """
    Načte diagram z JSON souboru (s dialogem pro výběr souboru).
    
    Pokud soubor obsahuje hierarchii (verze 2), načte všechny canvasy včetně zoom-in hierarchií.
    Jinak načte pouze aktuální scénu (zpětná kompatibilita).
    
    Args:
        scene: Aktuální scéna (použije se pokud new_tab=False a není hierarchie)
        allowed_link: Callback pro validaci vazeb
        new_canvas_callback: Funkce pro vytvoření nového tabu
        new_tab: Pokud True, načte do nového tabu; jinak do aktuální scény
        main_window: MainWindow instance pro načtení hierarchií (pokud None, jen aktuální scéna)
    """
    caption = "Import OPD"
    path, _ = QFileDialog.getOpenFileName(None, caption, "", "JSON (*.json)")
    if not path:
        return
    
    # Načtení JSON souboru
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Zkontroluj verzi/formát
    meta = data.get("meta", {})
    format_version = meta.get("version", 1)
    format_type = meta.get("format", "opm-mvp-json")
    
    # Pokud je to hierarchie (verze 2) a máme main_window, načteme celou hierarchii
    if format_version >= 2 and "hierarchy" in format_type and main_window:
        _load_hierarchy_from_json(main_window, data, allowed_link)
    else:
        # Zpětná kompatibilita - načteme jen aktuální scénu
        target_scene = scene
        if new_tab and new_canvas_callback:
            # Vytvoří nový tab s názvem podle souboru
            base = os.path.splitext(os.path.basename(path))[0] or "Canvas"
            view = new_canvas_callback(base)
            target_scene = view.scene()

        # Načtení dat do scény
        dict_to_scene(target_scene, data, allowed_link)


def _load_hierarchy_from_json(main_window, data: Dict[str, Any], allowed_link):
    """
    Načte hierarchii diagramu včetně všech zoom-in canvasů.
    
    Args:
        main_window: MainWindow instance
        data: Načtená data z JSON
        allowed_link: Callback pro validaci vazeb
    """
    # Nejdřív vymažeme všechny existující taby (kromě root)
    # nebo vytvoříme nový root canvas
    nodes = data.get("nodes", [])
    links = data.get("links", [])
    
    # Vytvoříme procesní mapu (process_id -> process_data)
    process_map = {n["id"]: n for n in nodes if n.get("kind") == "process"}
    
    # Najdeme procesy, které mají podprocesy/objekty (ty potřebují in-zoom canvas)
    processes_with_children = set()
    for node in nodes:
        parent_id = node.get("parent_process_id")
        if parent_id and parent_id in process_map:
            processes_with_children.add(parent_id)
    
    # Uložíme data do globálního modelu
    main_window._global_diagram_data = {
        "nodes": nodes,
        "links": links,
        "meta": data.get("meta", {})
    }
    
    # Vytvoříme root canvas a načteme do něj prvky s parent_process_id == None
    # Nejdřív smažeme všechny existující taby
    while main_window.tabs.count() > 0:
        main_window.tabs.removeTab(0)
    
    # Vytvoříme root canvas
    root_name = "🏠 Root Canvas"
    if hasattr(main_window, '_root_canvas_name'):
        root_name = main_window._root_canvas_name
    root_view = main_window._new_canvas(root_name)
    root_scene = root_view.scene()
    
    # Ujistíme se, že root_canvas_name je nastaveno
    if hasattr(main_window, '_root_canvas_name'):
        main_window._root_canvas_name = root_name
    
    # Načteme root prvky (parent_process_id == None)
    root_data = {
        "nodes": [n for n in nodes if n.get("parent_process_id") is None],
        "links": [],  # Linky se načtou podle uzlů
        "meta": data.get("meta", {})
    }
    
    # Načteme linky, které spojují root uzly
    root_node_ids = {n["id"] for n in root_data["nodes"]}
    root_data["links"] = [
        l for l in links
        if l.get("src") in root_node_ids and l.get("dst") in root_node_ids
    ]
    
    dict_to_scene(root_scene, root_data, allowed_link)
    
    # Pro každý proces s podprocesy vytvoříme in-zoom canvas
    # Musíme to dělat rekurzivně, ale nejdřív vytvoříme všechny procesy v root scéně
    # Pak projdeme hierarchii a vytvoříme in-zoom canvasy
    
    def create_in_zoom_canvases(parent_process_id: str | None, parent_view):
        """Rekurzivně vytvoří in-zoom canvasy pro všechny procesy s dětmi."""
        # Najdi procesy, které patří do tohoto parent_process_id
        child_processes = [
            p for p in process_map.values()
            if p.get("parent_process_id") == parent_process_id
        ]
        
        for process in child_processes:
            process_id = process["id"]
            
            # Pokud má tento proces děti, vytvoř pro něj in-zoom canvas
            if process_id in processes_with_children:
                # Vytvoř in-zoom canvas
                tab_title = f"🔍 {process.get('label', 'Process')}"
                zoom_view = main_window._new_canvas(
                    title=tab_title,
                    parent_view=parent_view,
                    zoomed_process_id=process_id
                )
                zoom_scene = zoom_view.scene()
                
                # Načti prvky pro tento proces
                process_data = {
                    "nodes": [n for n in nodes if n.get("parent_process_id") == process_id],
                    "links": [],
                    "meta": data.get("meta", {})
                }
                
                # Načti linky pro tento proces
                process_node_ids = {n["id"] for n in process_data["nodes"]}
                process_data["links"] = [
                    l for l in links
                    if l.get("src") in process_node_ids and l.get("dst") in process_node_ids
                ]
                
                dict_to_scene(zoom_scene, process_data, allowed_link)
                
                # Rekurzivně vytvoř canvasy pro podprocesy
                create_in_zoom_canvases(process_id, zoom_view)
    
    # Začněme s root procesy
    create_in_zoom_canvases(None, root_view)
    
    # Přepneme na root canvas
    main_window.tabs.setCurrentIndex(0)
    
    # Refresh hierarchie
    if hasattr(main_window, 'refresh_hierarchy_panel'):
        main_window.refresh_hierarchy_panel()