"""Hlavní okno aplikace OPM Editor."""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QAction,
    QImage,
    QPainter,
    QUndoStack,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsItem,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)
from PySide6.QtSvg import QSvgGenerator

from constants import *
from graphics.grid import GridScene
from graphics.nodes import ObjectItem, ProcessItem, StateItem
from graphics.link import LinkItem
from ui.view import EditorView
from ui.tabs import RenameableTabBar
from ui.toolbar import ToolbarManager
from ui.properties_panel import PropertiesPanel
from ui.simulation_panel import SimulationPanel
from ui.dialogs import show_opl_import_dialog, show_nl_to_opl_dialog, show_opl_preview_dialog
from persistence.json_io import safe_base_filename
from undo.commands import DeleteItemsCommand, ClearAllCommand, AddStateCommand, AddNodeCommand, PasteItemsCommand


class MainWindow(QMainWindow):
    """Hlavní okno aplikace OPM Editor."""
    
    _instance = None
    
    @classmethod
    def instance(cls):
        """Vrátí instanci MainWindow (singleton pattern)."""
        return cls._instance
    
    def __init__(self):
        super().__init__()
        MainWindow._instance = self
        self.setWindowTitle("OPM Editor — MVP")
        
        # Inicializace stavových proměnných
        self.mode = Mode.SELECT
        self._scale = 1.0
        self.pending_link_src: Optional[QGraphicsItem] = None
        self.default_link_type = "consumption/result"  # Výchozí typ vazby
        self._suppress_combo = False
        
        # Undo stack
        self.undo_stack = QUndoStack(self)
        
        # Clipboard pro copy-paste
        self.clipboard = None
        
        # Globální datový model pro všechny canvasy
        self._global_diagram_data = {
            "nodes": [],  # Seznam všech uzlů (včetně podprocesů)
            "links": [],  # Seznam všech vazeb
            "meta": {"format": "opm-mvp-json", "version": 1}
        }
        
        # Název root canvasu (pro synchronizaci s hierarchií)
        self._root_canvas_name = "🏠 Root Canvas"
        
        # Ochrana proti rekurzivním voláním
        self._is_syncing = False
        self._is_refreshing_hierarchy = False
        self._is_navigating = False
        
        # Inicializace UI
        self._init_tabs()
        self._init_first_canvas()
        self._init_actions()
        # Nejprve vytvoř dokovací panely, aby na ně mohl toolbar/menu odkazovat
        self._init_properties_panel()
        self._init_hierarchy_panel()
        self._init_simulation_panel()
        self._init_toolbars()
    
    def _init_tabs(self):
        """Inicializuje tab widget."""
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        
        bar = RenameableTabBar(self.tabs)
        self.tabs.setTabBar(bar)
        bar.renameRequested.connect(self._rename_tab)
    
    def _init_first_canvas(self):
        """Vytvoří první canvas."""
        self._new_canvas("🏠 Root Canvas")
    
    def _init_actions(self):
        """Inicializuje akce a klávesové zkratky."""
        # Select All (Ctrl+A)
        select_all_action = QAction("Označit vše", self)
        select_all_action.setShortcut(QKeySequence.SelectAll)
        select_all_action.triggered.connect(self.select_all)
        self.addAction(select_all_action)
        
        # Copy (Ctrl+C)
        copy_action = QAction("Kopírovat", self)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.triggered.connect(self.copy_selection)
        self.addAction(copy_action)
        
        # Paste (Ctrl+V)
        paste_action = QAction("Vložit", self)
        paste_action.setShortcut(QKeySequence.Paste)
        paste_action.triggered.connect(self.paste_selection)
        self.addAction(paste_action)
        
        # Duplicate (Ctrl+D)
        duplicate_action = QAction("Duplikovat", self)
        duplicate_action.setShortcut(QKeySequence("Ctrl+D"))
        duplicate_action.triggered.connect(self.duplicate_selection)
        self.addAction(duplicate_action)
    
    def _init_toolbars(self):
        """Inicializuje toolbary."""
        toolbar_manager = ToolbarManager(self)
        toolbar_manager.create_all_toolbars()
    
    def _init_properties_panel(self):
        """Inicializuje properties panel."""
        self.dock_props = PropertiesPanel(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_props)
        
        # Připojí změnu výběru na panel
        print("[Init] Connecting properties panel to scene.selectionChanged")
        self.scene.selectionChanged.connect(self.update_properties_panel)
        self.update_properties_panel()
    
    def _init_hierarchy_panel(self):
        """Inicializuje hierarchický panel."""
        from ui.hierarchy_panel import ProcessHierarchyPanel
        self.dock_hierarchy = ProcessHierarchyPanel(self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_hierarchy)
        self.dock_hierarchy.refresh_tree()
    
    def _init_simulation_panel(self):
        """Inicializuje simulační panel."""
        self.dock_simulation = SimulationPanel(self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_simulation)
        # Simulace panel bude umístěn hned po properties panelem (vertikálně rozdělený prostor)
        self.splitDockWidget(self.dock_props, self.dock_simulation, Qt.Vertical)
    
    # ========== Pomocné metody ==========
    
    def push_cmd(self, cmd):
        """Přidá příkaz na undo stack."""
        self.undo_stack.push(cmd)
    
    def snap(self, p: QPointF) -> QPointF:
        """Přichytí bod na mřížku."""
        return QPointF(
            round(p.x() / GRID_SIZE) * GRID_SIZE,
            round(p.y() / GRID_SIZE) * GRID_SIZE
        )
    
    def selected_item(self) -> Optional[QGraphicsItem]:
        """Vrátí první vybraný prvek nebo None."""
        sel = self.scene.selectedItems()
        return sel[0] if sel else None
    
    def select_all(self):
        """Označí všechny prvky v aktuální scéně."""
        if not hasattr(self, 'scene') or self.scene is None:
            return
        
        # Označíme všechny prvky, které jsou označitelné
        for item in self.scene.items():
            if item.flags() & QGraphicsItem.ItemIsSelectable:
                item.setSelected(True)
        
        self.statusBar().showMessage(f"Označeno {len(self.scene.selectedItems())} prvků", 2000)
    
    def copy_selection(self):
        """Zkopíruje vybrané prvky do schránky."""
        if not hasattr(self, 'scene') or self.scene is None:
            return
        
        selected = self.scene.selectedItems()
        if not selected:
            self.statusBar().showMessage("Nic nevybráno ke kopírování", 2000)
            return
        
        # Sebereme vybrané uzly (ObjectItem, ProcessItem, StateItem)
        nodes = []
        links = []
        selected_node_ids = set()
        
        # Nejdřív sebereme všechny vybrané uzly
        for item in selected:
            if isinstance(item, (ObjectItem, ProcessItem)):
                node_data = self._serialize_node(item)
                nodes.append(node_data)
                selected_node_ids.add(item.node_id)
                
                # Pokud je objekt vybraný, zkopírujeme i jeho stavy
                if isinstance(item, ObjectItem):
                    for child in item.childItems():
                        if isinstance(child, StateItem):
                            state_data = self._serialize_state(child, item.node_id)
                            nodes.append(state_data)
                            selected_node_ids.add(child.node_id)
        
        # Sebereme linky mezi vybranými uzly
        for item in selected:
            if isinstance(item, LinkItem):
                # Kontrola, zda link spojuje vybrané uzly
                src_id = getattr(item.src, 'node_id', None)
                dst_id = getattr(item.dst, 'node_id', None)
                
                if src_id in selected_node_ids and dst_id in selected_node_ids:
                    link_data = self._serialize_link(item)
                    links.append(link_data)
        
        # Uložíme do schránky
        self.clipboard = {
            "nodes": nodes,
            "links": links
        }
        
        self.statusBar().showMessage(f"Zkopírováno {len(nodes)} prvků a {len(links)} vazeb", 2000)
    
    def paste_selection(self):
        """Vloží prvky ze schránky."""
        if not hasattr(self, 'scene') or self.scene is None:
            return
        
        if not self.clipboard or not self.clipboard.get("nodes"):
            self.statusBar().showMessage("Schránka je prázdná", 2000)
            return
        
        # Vytvoříme příkaz pro vložení
        cmd = PasteItemsCommand(self.scene, self.clipboard, QPointF(30, 30))
        self.push_cmd(cmd)
        
        # Označíme vložené prvky
        self.scene.clearSelection()
        for item in cmd.pasted_items:
            item.setSelected(True)
        
        self.statusBar().showMessage(f"Vloženo {len(cmd.pasted_items)} prvků", 2000)
    
    def duplicate_selection(self):
        """Duplikuje vybrané prvky (copy + paste v jednom kroku)."""
        self.copy_selection()
        self.paste_selection()
    
    def _serialize_node(self, item):
        """Serializuje uzel do slovníku."""
        pos = item.pos()
        rect = item.rect()
        return {
            "id": item.node_id,
            "kind": item.kind,
            "label": item.label,
            "x": pos.x(),
            "y": pos.y(),
            "w": rect.width(),
            "h": rect.height(),
            "essence": getattr(item, 'essence', 'physical'),
            "affiliation": getattr(item, 'affiliation', 'systemic'),
            "parent_process_id": getattr(item, 'parent_process_id', None)
        }
    
    def _serialize_state(self, state, parent_id):
        """Serializuje stav do slovníku."""
        rect = state.rect()
        return {
            "id": state.node_id,
            "kind": "state",
            "label": state.label,
            "x": rect.x(),
            "y": rect.y(),
            "w": rect.width(),
            "h": rect.height(),
            "parent_id": parent_id
        }
    
    def _serialize_link(self, link):
        """Serializuje link do slovníku."""
        return {
            "id": getattr(link, 'link_id', 'link_' + str(id(link))),
            "src": getattr(link.src, 'node_id', ''),
            "dst": getattr(link.dst, 'node_id', ''),
            "link_type": link.link_type,
            "label": link.label,
            "card_src": getattr(link, 'card_src', ''),
            "card_dst": getattr(link, 'card_dst', '')
        }
    
    # ========== Global data model synchronization ==========
    
    def sync_scene_to_global_model(self, scene=None, parent_process_id=None):
        """
        Synchronizuje scénu do globálního datového modelu.
        
        Args:
            scene: Scéna k synchronizaci (default: aktuální scéna)
            parent_process_id: ID rodičovského procesu pro tuto scénu
        """
        # Ochrana proti rekurzivním voláním
        if self._is_syncing:
            return
        
        self._is_syncing = True
        try:
            if scene is None:
                scene = self.scene
            
            from persistence.json_io import scene_to_dict
            from opd.models import DiagramNode, DiagramLink
            
            # Převeď scénu na slovník
            scene_data = scene_to_dict(scene)
            
            # Nastav parent_process_id pro uzly v této scéně
            for node in scene_data["nodes"]:
                if node.get("kind") in ("object", "process"):
                    node["parent_process_id"] = parent_process_id
            
            # Odstraň staré uzly a linky z této scény
            self._global_diagram_data["nodes"] = [
                n for n in self._global_diagram_data["nodes"]
                if n.get("parent_process_id") != parent_process_id
            ]
            
            # Přidej nové uzly a linky
            self._global_diagram_data["nodes"].extend(scene_data["nodes"])
            
            # Pro linky odstraníme ty, které souvisí s uzly z této scény
            scene_node_ids = {n["id"] for n in scene_data["nodes"]}
            self._global_diagram_data["links"] = [
                l for l in self._global_diagram_data.get("links", [])
                if l.get("src") not in scene_node_ids and l.get("dst") not in scene_node_ids
            ]
            self._global_diagram_data["links"].extend(scene_data["links"])
            
            # Refresh hierarchického panelu
            self.refresh_hierarchy_panel()
        except Exception as e:
            print(f"Error in sync_scene_to_global_model: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_syncing = False
    
    def sync_global_model_to_scene(self, scene, parent_process_id=None):
        """
        Načte data z globálního modelu do scény.
        
        Args:
            scene: Cílová scéna
            parent_process_id: ID procesu, jehož podprocesy chceme načíst
        """
        try:
            print(f"[Sync] Loading data into scene for parent_process_id={parent_process_id}")
            
            from persistence.json_io import dict_to_scene
            
            # Vyfiltruj uzly a linky pro tuto scénu
            filtered_nodes = [
                n for n in self._global_diagram_data["nodes"]
                if n.get("parent_process_id") == parent_process_id
            ]
            
            print(f"[Sync] Found {len(filtered_nodes)} nodes")
            
            # Vytvoř množinu ID uzlů v této scéně
            node_ids = {n["id"] for n in filtered_nodes}
            
            # Vyfiltruj linky, které spojují uzly v této scéně
            filtered_links = [
                l for l in self._global_diagram_data.get("links", [])
                if l.get("src") in node_ids and l.get("dst") in node_ids
            ]
            
            print(f"[Sync] Found {len(filtered_links)} links")
            
            # Načti data do scény
            filtered_data = {
                "nodes": filtered_nodes,
                "links": filtered_links,
                "meta": self._global_diagram_data.get("meta", {})
            }
            
            dict_to_scene(scene, filtered_data, self.allowed_link)
            print(f"[Sync] Scene loaded successfully")
            
        except Exception as e:
            print(f"[ERROR] sync_global_model_to_scene failed: {e}")
            import traceback
            traceback.print_exc()
    
    def refresh_hierarchy_panel(self):
        """Obnoví hierarchický panel."""
        # Ochrana proti rekurzivním voláním
        if self._is_refreshing_hierarchy:
            return
        
        self._is_refreshing_hierarchy = True
        try:
            if hasattr(self, 'dock_hierarchy'):
                self.dock_hierarchy.refresh_tree()
        except Exception as e:
            print(f"Error in refresh_hierarchy_panel: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_refreshing_hierarchy = False
    
    def navigate_into_process_by_id(self, process_id: str, parent_process_id: Optional[str]):
        """
        Naviguje do in-zoom view procesu podle jeho ID.
        
        Args:
            process_id: ID procesu
            parent_process_id: ID rodičovského procesu (None pro root)
        """
        print(f"[Navigate] Request to navigate to process_id={process_id}, parent={parent_process_id}")
        
        # Ochrana proti rekurzivním voláním
        if self._is_navigating:
            print("[Navigate] Already navigating, skipping...")
            return
        
        self._is_navigating = True
        try:
            # Najdi proces v datovém modelu
            process_node = None
            for n in self._global_diagram_data["nodes"]:
                if n["id"] == process_id and n["kind"] == "process":
                    process_node = n
                    break
            
            if not process_node:
                print(f"[Navigate] Process not found: {process_id}")
                return
            
            print(f"[Navigate] Found process: {process_node['label']}")
            
            # Najdi scénu, ve které je proces
            parent_view = self._find_view_for_parent_process_id(parent_process_id)
            if not parent_view:
                # Pokud není view pro parent, zkus najít v root view
                parent_view = self._find_root_view()
            
            if not parent_view:
                print("[Navigate] Parent view not found!")
                return
            
            print(f"[Navigate] Found parent view")
            
            # Hledej existující in-zoom tab
            existing_tab_idx = self._find_in_zoom_tab_for_process(process_id, parent_view)
            if existing_tab_idx >= 0:
                print(f"[Navigate] Switching to existing tab {existing_tab_idx}")
                self.tabs.setCurrentIndex(existing_tab_idx)
                # Aktualizuj properties panel
                self.update_properties_panel()
                return
            
            print(f"[Navigate] Creating new in-zoom tab")
            
            # Vytvoř nový in-zoom tab
            tab_title = f"🔍 {process_node['label']}"
            
            # Vytvoř nový view
            new_view = self._new_canvas(
                title=tab_title,
                parent_view=parent_view,
                zoomed_process_id=process_id
            )
            
            if not new_view:
                print("[Navigate] Failed to create new view!")
                return
            
            # Načti data do nové scény
            self.sync_global_model_to_scene(new_view.scene(), process_id)
            
            # Aktualizuj properties panel pro nový view
            self.update_properties_panel()
            
            self.statusBar().showMessage(f"In-zoom: {process_node['label']}", 2000)
            print(f"[Navigate] Navigation completed successfully")
            
        except Exception as e:
            print(f"[ERROR] navigate_into_process_by_id failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_navigating = False
    
    def _find_view_for_parent_process_id(self, parent_process_id):
        """Najde view pro daný parent_process_id."""
        if parent_process_id is None:
            return self._find_root_view()
        
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if hasattr(view, 'zoomed_process_id') and view.zoomed_process_id == parent_process_id:
                return view
        return None
    
    def _find_root_view(self):
        """Najde root view (view bez parent_view)."""
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if not hasattr(view, 'parent_view') or view.parent_view is None:
                return view
        return None
    
    def navigate_to_root_canvas(self):
        """Naviguje na root canvas (top-level view)."""
        root_view = self._find_root_view()
        if root_view:
            # Najdi index root view
            root_idx = self._find_tab_index_for_view(root_view)
            if root_idx >= 0:
                self.tabs.setCurrentIndex(root_idx)
                # Aktualizuj properties panel
                self.update_properties_panel()
                self.statusBar().showMessage("Root canvas", 2000)
    
    def _rename_process_by_id(self, process_id: str, new_label: str):
        """
        Přejmenuje proces v globálním modelu a ve všech view.
        
        Args:
            process_id: ID procesu k přejmenování
            new_label: Nový název
        """
        # Aktualizuj v globálním modelu
        for node in self._global_diagram_data["nodes"]:
            if node["id"] == process_id and node["kind"] == "process":
                node["label"] = new_label
                break
        
        # Najdi a aktualizuj proces ve všech otevřených view
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            scene = view.scene()
            
            # Hledej proces v této scéně
            for item in scene.items():
                if hasattr(item, 'node_id') and item.node_id == process_id:
                    from graphics.nodes import ProcessItem
                    if isinstance(item, ProcessItem):
                        item.set_label(new_label)
                        break
            
            # Aktualizuj název tabu, pokud je to in-zoom view tohoto procesu
            if hasattr(view, 'zoomed_process_id') and view.zoomed_process_id == process_id:
                self.tabs.setTabText(i, f"🔍 {new_label}")
        
        # Refresh hierarchického panelu
        self.refresh_hierarchy_panel()
    
    # ========== Tab management ==========
    
    def _new_canvas(self, title: str | None = None, parent_view=None, zoomed_process_id=None):
        """Vytvoří nový canvas v novém tabu."""
        scene = GridScene(self)
        scene.setSceneRect(-5000, -5000, 10000, 10000)

        view = EditorView(scene, self, parent_view=parent_view, zoomed_process_id=zoomed_process_id)
        
        # Pokud je to in-zoom, zaregistruj ho u rodiče
        if parent_view is not None:
            parent_view.child_views.append(view)
        
        idx = self.tabs.addTab(view, title or f"Canvas {self.tabs.count() + 1}")
        self.tabs.setCurrentIndex(idx)

        self._activate_view(view)
        return view

    def create_in_zoom_canvas(self, process_item):
        """
        Vytvoří in-zoom canvas pro daný proces, nebo přepne na existující.
        
        Args:
            process_item: ProcessItem, jehož vnitřek chceme modelovat
        """
        current_view = self.view
        
        # Nejprve synchronizuj aktuální scénu do globálního modelu
        self.sync_scene_to_global_model(self.scene, getattr(current_view, 'zoomed_process_id', None))
        
        # Nejprve zkontroluj, zda už existuje in-zoom tab pro tento proces
        existing_tab_idx = self._find_in_zoom_tab_for_process(process_item.node_id, current_view)
        if existing_tab_idx >= 0:
            # Tab už existuje, přepni na něj
            self.tabs.setCurrentIndex(existing_tab_idx)
            self.statusBar().showMessage(f"Přepnuto na existující in-zoom: {process_item.label}", 2000)
            return
        
        # Tab neexistuje, vytvoř nový
        # Název tabu podle procesu
        tab_title = f"🔍 {process_item.label}"
        
        # Vytvoř nový in-zoom canvas
        new_view = self._new_canvas(
            title=tab_title,
            parent_view=current_view,
            zoomed_process_id=process_item.node_id
        )
        
        # Načti data z globálního modelu do nové scény
        self.sync_global_model_to_scene(new_view.scene(), process_item.node_id)
        
        self.statusBar().showMessage(f"In-zoom: {process_item.label}", 2000)
    
    def _find_in_zoom_tab_for_process(self, process_id: str, parent_view):
        """
        Najde existující in-zoom tab pro daný proces a parent view.
        
        Args:
            process_id: ID procesu, jehož in-zoom hledáme
            parent_view: Rodičovský view, ze kterého byl in-zoom vytvořen
            
        Returns:
            Index tabu nebo -1, pokud nebyl nalezen
        """
        for i in range(self.tabs.count()):
            view = self.tabs.widget(i)
            if (hasattr(view, 'zoomed_process_id') and 
                view.zoomed_process_id == process_id and
                hasattr(view, 'parent_view') and
                view.parent_view == parent_view):
                return i
        return -1
    
    def navigate_to_parent(self):
        """Naviguje zpět na parent view (out-zoom)."""
        if hasattr(self.view, 'parent_view') and self.view.parent_view is not None:
            # Najdi tab index parent view
            parent_idx = self._find_tab_index_for_view(self.view.parent_view)
            if parent_idx >= 0:
                self.tabs.setCurrentIndex(parent_idx)
                self.statusBar().showMessage("Out-zoom", 2000)
    
    def update_out_zoom_button_visibility(self):
        """Aktualizuje viditelnost out-zoom tlačítka podle aktuálního view."""
        if hasattr(self, 'act_out_zoom'):
            has_parent = (hasattr(self.view, 'parent_view') and 
                         self.view.parent_view is not None)
            self.act_out_zoom.setVisible(has_parent)
    
    def _find_tab_index_for_view(self, view):
        """Najde index tabu pro daný view."""
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) == view:
                return i
        return -1

    def _activate_view(self, view):
        """Aktivuje daný view a připojí signály."""
        try:
            print(f"[Activate] Activating view with zoomed_process_id={getattr(view, 'zoomed_process_id', None)}")
            
            # Synchronizuj starý view do globálního modelu před přepnutím
            # ale jen pokud není již synchronizace v běhu
            if hasattr(self, 'view') and hasattr(self, 'scene') and not self._is_syncing:
                old_parent_process_id = getattr(self.view, 'zoomed_process_id', None)
                print(f"[Activate] Syncing old view with parent_process_id={old_parent_process_id}")
                self.sync_scene_to_global_model(self.scene, old_parent_process_id)
            
            # Odpojí staré signály
            try:
                if hasattr(self, 'scene'):
                    print(f"[Activate] Disconnecting old signals")
                    self.scene.selectionChanged.disconnect(self.sync_selected_to_props)
                    self.scene.selectionChanged.disconnect(self.update_properties_panel)
            except Exception as e:
                print(f"[Activate] Could not disconnect old signals: {e}")
                pass
            
            # Zkontroluj, že view a scene existují
            if not view:
                print("[ERROR] View is None!")
                return
            
            scene = view.scene()
            if not scene:
                print("[ERROR] Scene is None!")
                return
            
            self.view = view
            self.scene = scene
            
            print(f"[Activate] Connecting selectionChanged signals")
            # Připoj signály
            self.scene.selectionChanged.connect(self.sync_selected_to_props)
            self.scene.selectionChanged.connect(self.update_properties_panel)

            # Vyčistí overlaye/stav linku
            self.view.clear_overlays()
            self.pending_link_src = None
            
            # Aktualizuj viditelnost out-zoom tlačítka
            self.update_out_zoom_button_visibility()
            
            # Aktualizuj properties panel
            self.update_properties_panel()
            
            print(f"[Activate] View activated successfully")
        except Exception as e:
            print(f"[ERROR] _activate_view failed: {e}")
            import traceback
            traceback.print_exc()

    def _current_tab_title(self) -> str:
        """Vrátí text aktivní záložky nebo fallback."""
        idx = self.tabs.currentIndex() if hasattr(self, "tabs") else -1
        if idx >= 0:
            t = self.tabs.tabText(idx).strip()
            return t if t else "Canvas"
        return "Canvas"

    def _on_tab_changed(self, idx: int):
        """Handler pro změnu tabu."""
        if idx < 0:
            return
        view = self.tabs.widget(idx)
        self._activate_view(view)

    def _close_current_tab(self):
        """Zavře aktuální tab."""
        idx = self.tabs.currentIndex()
        self._close_tab_at_index(idx)
    
    def _close_tab_at_index(self, idx: int):
        """Zavře tab na daném indexu."""
        if idx >= 0 and idx < self.tabs.count():
            self.tabs.removeTab(idx)
        
        # Když nic nezbyde, založí prázdný canvas
        if self.tabs.count() == 0:
            self._new_canvas("🏠 Root Canvas")

    def _rename_tab(self, idx: int):
        """Přejmenuje tab a odpovídající proces."""
        if idx < 0 or idx >= self.tabs.count():
            return
        
        view = self.tabs.widget(idx)
        current = self.tabs.tabText(idx)
        
        # Odstraň emoji prefix pro editaci
        current_clean = current.replace("🔍 ", "").replace("🏠 ", "").strip()
        
        text, ok = QInputDialog.getText(self, "Rename OPD", "New name:", text=current_clean)
        if ok:
            new = text.strip()
            if new:
                # Pokud je to in-zoom view, přejmenuj proces
                if hasattr(view, 'zoomed_process_id') and view.zoomed_process_id:
                    self._rename_process_by_id(view.zoomed_process_id, new)
                    # Aktualizuj název tabu
                    self.tabs.setTabText(idx, f"🔍 {new}")
                else:
                    # Root canvas - přejmenuj tab a aktualizuj globální název
                    new_name = f"🏠 {new}"
                    self.tabs.setTabText(idx, new_name)
                    self._root_canvas_name = new_name
                    # Refresh hierarchického panelu
                    self.refresh_hierarchy_panel()
    
    # ========== Mode & zoom ==========
    
    def set_mode(self, mode: str):
        """Nastaví režim editoru."""
        self.mode = mode
        
        # Zrušit výběr všech prvků při přepnutí nástroje
        self.scene.clearSelection()
        
        try:
            if hasattr(self, 'actions') and mode in self.actions:
                self.actions[mode].setChecked(True)
        except Exception:
            pass
        
        if mode == Mode.SELECT:
            self.view.setCursor(Qt.ArrowCursor)
            self.view.setDragMode(EditorView.RubberBandDrag)
            self.view.clear_overlays()
        else:
            self.view.setCursor(Qt.CrossCursor)
            self.view.setDragMode(EditorView.NoDrag)
        
        self.statusBar().showMessage(f"Mode: {mode}")
        
        if mode != Mode.ADD_LINK:
            self.pending_link_src = None
            self.view.clear_temp_link()
        
        # Vynutit okamžitou aktualizaci ghost overlay pro nový mód
        if mode in (Mode.ADD_OBJECT, Mode.ADD_PROCESS, Mode.ADD_STATE):
            # Získat aktuální pozici kurzoru
            cursor_pos = self.view.mapFromGlobal(self.view.cursor().pos())
            scene_pos = self.view.mapToScene(cursor_pos)
            self.view.update_ghost(scene_pos)

    def set_zoom(self, scale: float):
        """Nastaví konkrétní úroveň zoomu."""
        # Omezení rozsahu
        scale = max(0.2, min(scale, 5.0))
        
        # Vypočítej faktor změny
        if self._scale > 0:
            factor = scale / self._scale
        else:
            factor = scale
        
        # Aplikuj změnu
        self._scale = scale
        self.view.resetTransform()
        self.view.scale(scale, scale)
        
        # Aktualizuj UI
        self._update_zoom_ui()
    
    def _update_zoom_ui(self):
        """Aktualizuje UI prvky pro zoom (slider a label)."""
        if hasattr(self, 'zoom_slider') and hasattr(self, 'zoom_value_label'):
            # Dočasně odpojíme signal, aby se zabránilo rekurzi
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(int(self._scale * 100))
            self.zoom_slider.blockSignals(False)
            self.zoom_value_label.setText(f"{int(self._scale * 100)}%")

    def zoom_in(self):
        """Přiblíží view."""
        new_scale = min(self._scale * 1.2, 5.0)
        self.set_zoom(new_scale)

    def zoom_out(self):
        """Oddálí view."""
        new_scale = max(self._scale / 1.2, 0.2)
        self.set_zoom(new_scale)

    def zoom_reset(self):
        """Resetuje zoom."""
        self.set_zoom(1.0)
    
    # ========== Node operations ==========
    
    def add_object(self, pos: QPointF):
        """Přidá nový objekt."""
        item = ObjectItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H))
        item.setPos(self.snap(pos))
        # Nastav parent_process_id podle aktuálního view
        if hasattr(self.view, 'zoomed_process_id'):
            item.parent_process_id = self.view.zoomed_process_id
        cmd = AddNodeCommand(self.scene, item, "Add Object")
        self.push_cmd(cmd)

    def add_process(self, pos: QPointF):
        """Přidá nový proces."""
        item = ProcessItem(QRectF(-NODE_W/2, -NODE_H/2, NODE_W, NODE_H))
        item.setPos(self.snap(pos))
        # Nastav parent_process_id podle aktuálního view
        if hasattr(self.view, 'zoomed_process_id'):
            item.parent_process_id = self.view.zoomed_process_id
        cmd = AddNodeCommand(self.scene, item, "Add Process")
        self.push_cmd(cmd)

    def add_state(self, obj: ObjectItem, pos_in_scene: QPointF):
        """Přidá nový stav do objektu."""
        p = obj.mapFromScene(self.snap(pos_in_scene))
        r = obj.rect()
        x = min(max(p.x()-STATE_W/2, r.left()+6), r.right()-STATE_W-6)
        y = min(max(p.y()-STATE_H/2, r.top()+6), r.bottom()-STATE_H-6)
        rect = QRectF(x, y, STATE_W, STATE_H)
        self.push_cmd(AddStateCommand(self.scene, obj, rect, "State"))
    
    # ========== Link operations ==========
    
    def _determine_consumption_result_type(self, src_item: QGraphicsItem, dst_item: QGraphicsItem) -> str:
        """Automaticky určí typ vazby (consumption nebo result) podle zdroje a cíle.
        
        Pokud je zdrojem Objekt nebo jeho Stav a cílem Proces, pak se jedná o consumption.
        Pokud je zdrojem Proces a cílem Objekt nebo jeho Stav, pak je to result.
        """
        src_is_object_or_state = isinstance(src_item, (ObjectItem, StateItem))
        dst_is_process = isinstance(dst_item, ProcessItem)
        src_is_process = isinstance(src_item, ProcessItem)
        dst_is_object_or_state = isinstance(dst_item, (ObjectItem, StateItem))
        
        if src_is_object_or_state and dst_is_process:
            return "consumption"
        elif src_is_process and dst_is_object_or_state:
            return "result"
        # Pokud není žádná z těchto kombinací, vrátíme výchozí hodnotu
        return "consumption"
    
    def _resolve_link_type(self, src_item: QGraphicsItem, dst_item: QGraphicsItem, link_type: str) -> str:
        """Převede 'consumption/result' na konkrétní typ podle zdroje a cíle."""
        if link_type == "consumption/result":
            return self._determine_consumption_result_type(src_item, dst_item)
        return link_type
    
    def allowed_link(self, src_item: QGraphicsItem, dst_item: QGraphicsItem, link_type: str) -> tuple[bool, str]:
        """Kontroluje, zda je link povolen."""
        # Pokud je to consumption/result, převedeme na konkrétní typ pro validaci
        resolved_type = self._resolve_link_type(src_item, dst_item, link_type)
        
        # Zjištění typů uzlů
        src_is_process = isinstance(src_item, ProcessItem)
        src_is_object = isinstance(src_item, ObjectItem)
        dst_is_process = isinstance(dst_item, ProcessItem)
        dst_is_object = isinstance(dst_item, ObjectItem)
        
        # Kontrola pro strukturální vztahy
        if resolved_type in STRUCTURAL_TYPES:
            # Strukturální vztahy mohou být pouze mezi stejnými typy uzlů
            # Exhibition může být mezi libovolnými uzly (objekt-objekt, proces-proces, objekt-proces)
            if resolved_type == "exhibition":
                if (src_is_process or src_is_object) and (dst_is_process or dst_is_object):
                    return True, ""
            
            # Ostatní strukturální vztahy pouze proces→proces nebo objekt→objekt
            if src_is_process and dst_is_process:
                return True, ""
            elif src_is_object and dst_is_object:
                return True, ""
            else:
                return False, f"Strukturální vztah '{resolved_type}' může být pouze mezi stejnými typy uzlů (proces-proces nebo objekt-objekt)."
        
        # Kontrola pro procedurální vazby
        if resolved_type in PROCEDURAL_TYPES:
            # Procedurální vazby NESMÍ být mezi stejnými typy uzlů (objekt-objekt nebo proces-proces)
            if src_is_object and dst_is_object:
                return False, f"Procedurální vazba '{resolved_type}' nemůže být mezi objekty. Procedurální vazby mohou být pouze mezi procesy a objekty."
            if src_is_process and dst_is_process:
                return False, f"Procedurální vazba '{resolved_type}' nemůže být mezi procesy. Procedurální vazby mohou být pouze mezi procesy a objekty."
            # Procedurální vazby jsou povoleny mezi procesy a objekty (v libovolném směru)
            return True, ""
        
        # Neznámý typ vazby - povolíme (pro jistotu)
        return True, ""

    def toggle_token(self, item):
        """Přepne token na objektu nebo stavu."""
        from graphics.nodes import ObjectItem, StateItem
        if not isinstance(item, (ObjectItem, StateItem)):
            return
        
        from undo.commands import ToggleTokenCommand
        cmd = ToggleTokenCommand(item, item.has_token)
        self.push_cmd(cmd)
    
    def handle_link_click(self, pos: QPointF):
        """Zpracuje kliknutí v režimu přidávání linku."""
        item = self.scene.itemAt(pos, self.view.transform())
        if not isinstance(item, (ObjectItem, ProcessItem, StateItem)):
            return
        
        if self.pending_link_src is None:
            self.pending_link_src = item
            self.statusBar().showMessage("Choose target node…")
        else:
            if item is self.pending_link_src:
                self.pending_link_src = None
                return
            
            # Automaticky určíme typ vazby, pokud je to consumption/result
            resolved_link_type = self._resolve_link_type(self.pending_link_src, item, self.default_link_type)
            
            ok, msg = self.allowed_link(self.pending_link_src, item, self.default_link_type)
            if not ok:
                QMessageBox.warning(self, "Neplatná vazba", msg)
                self.pending_link_src = None
                return

            self.scene.addItem(LinkItem(self.pending_link_src, item, resolved_link_type))
            self.pending_link_src = None
            self.statusBar().clearMessage()

    def cancel_link_creation(self):
        """Zruší tvorbu linku."""
        self.pending_link_src = None
        
        if hasattr(self, "view") and hasattr(self.view, "clear_temp_link"):
            self.view.clear_temp_link()
        
        sb = getattr(self, "statusBar", None)
        if callable(sb):
            self.statusBar().clearMessage()
    
    # ========== Delete operations ==========
    
    def delete_selected(self):
        """Smaže vybrané prvky."""
        items = self.scene.selectedItems()
        if not items:
            return
        self.push_cmd(DeleteItemsCommand(self.scene, items))

    def clear_all(self):
        """Smaže všechny prvky ze scény."""
        if not self.scene.items():
            return
        self.push_cmd(ClearAllCommand(self.scene))
    
    # ========== Properties panel ==========
    
    def update_properties_panel(self):
        """Aktualizuje properties panel."""
        print("[MainWindow] update_properties_panel called")
        if hasattr(self, 'dock_props'):
            self.dock_props.update_for_selection()
        else:
            print("[MainWindow] No dock_props!")
    
    def sync_selected_to_props(self):
        """Synchronizuje výběr do properties panelu."""
        print("[MainWindow] sync_selected_to_props called")
        if hasattr(self, 'dock_props'):
            self.dock_props.sync_selection_to_props()
        else:
            print("[MainWindow] No dock_props in sync_selected_to_props!")
    
    # ========== Dialogy ==========
    
    def import_opl_dialog(self):
        """Zobrazí dialog pro import OPL."""
        show_opl_import_dialog(self)

    def open_nl_to_opl_dialog(self):
        """Zobrazí dialog pro NL → OPL."""
        show_nl_to_opl_dialog(self)

    def preview_opl(self):
        """Zobrazí náhled generovaného OPL."""
        show_opl_preview_dialog(self.scene, self)
    
    # ========== Export ==========
    
    def export_image(self, kind: str = "png"):
        """Exportuje scénu jako obrázek."""
        base = safe_base_filename()

        if kind in "jpg":
            path, _ = QFileDialog.getSaveFileName(
                self, "Export JPG", f"{base}.jpg", "JPEG (*.jpg *.jpeg)"
            )
            if not path:
                return
            rb = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
            img = QImage(int(rb.width()), int(rb.height()), QImage.Format_RGB32)
            img.fill(Qt.white)
            painter = QPainter(img)
            self.scene.render(painter, target=QRectF(0, 0, rb.width(), rb.height()), source=rb)
            painter.end()
            img.save(path, "JPG", 95)

        elif kind == "png":
            path, _ = QFileDialog.getSaveFileName(
                self, "Export PNG", f"{base}.png", "PNG (*.png)"
            )
            if not path:
                return
            # Dočasně vypneme mřížku pro export
            original_grid_state = self.scene._draw_grid
            self.scene.set_draw_grid(False)
            try:
                rb = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
                img = QImage(int(rb.width()), int(rb.height()), QImage.Format_ARGB32_Premultiplied)
                img.fill(0x00FFFFFF)
                painter = QPainter(img)
                self.scene.render(painter, target=QRectF(0, 0, rb.width(), rb.height()), source=rb)
                painter.end()
                img.save(path)
            finally:
                # Vrátíme původní stav mřížky
                self.scene.set_draw_grid(original_grid_state)

        elif kind == "svg":
            path, _ = QFileDialog.getSaveFileName(
                self, "Export SVG", f"{base}.svg", "SVG (*.svg)"
            )
            if not path:
                return
            rb = self.scene.itemsBoundingRect().adjusted(-20, -20, 20, 20)
            gen = QSvgGenerator()
            gen.setFileName(path)
            gen.setSize(rb.size().toSize())
            gen.setViewBox(rb)
            painter = QPainter(gen)
            self.scene.render(painter, target=rb, source=rb)
            painter.end()

        else:
            QMessageBox.warning(self, "Export", f"Unsupported format: {kind}")
    
    # ========== Keyboard events ==========
    
    def keyPressEvent(self, event):
        """Zpracuje stisknutí klávesy."""
        # Mazání
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected()
            event.accept()
            return
        
        # Zrušení linku
        if (event.key() == Qt.Key_Escape 
                and self.mode == Mode.ADD_LINK 
                and self.pending_link_src is not None):
            self.cancel_link_creation()
            event.accept()
            return
        
        # Rychlé přepínání módu
        if event.key() == Qt.Key_P:
            # P = Přidat proces
            self.set_mode(Mode.ADD_PROCESS)
            event.accept()
            return
        
        if event.key() == Qt.Key_O:
            # O = Přidat objekt
            self.set_mode(Mode.ADD_OBJECT)
            event.accept()
            return
        
        if event.key() == Qt.Key_L:
            # L = Přidat link
            self.set_mode(Mode.ADD_LINK)
            event.accept()
            return
        
        if event.key() == Qt.Key_S:
            # S = Select tool
            self.set_mode(Mode.SELECT)
            event.accept()
            return
        
        if event.key() == Qt.Key_T:
            # T = Toggle token na vybraných objektech/stavech
            sel = self.scene.selectedItems()
            from graphics.nodes import ObjectItem, StateItem
            items_to_toggle = [it for it in sel if isinstance(it, (ObjectItem, StateItem))]
            if items_to_toggle:
                for item in items_to_toggle:
                    self.toggle_token(item)
                event.accept()
                return
            # Pokud není nic vybrané, klikněme na prvek pod kurzorem
            if self.mode == Mode.SELECT:
                cursor_pos = self.view.mapFromGlobal(self.view.cursor().pos())
                scene_pos = self.view.mapToScene(cursor_pos)
                item = self.scene.itemAt(scene_pos, self.view.transform())
                if isinstance(item, (ObjectItem, StateItem)):
                    self.toggle_token(item)
                    event.accept()
                    return
        
        # Rychlé přepínání typu linku čísly
        if event.key() in (Qt.Key_1, Qt.Key_2, Qt.Key_3, Qt.Key_4):
            mapping = {
                Qt.Key_1: "consumption/result",
                Qt.Key_2: "effect",
                Qt.Key_3: "agent",
                Qt.Key_4: "instrument",
            }
            lt = mapping.get(event.key())
            sel = [it for it in self.scene.selectedItems() if isinstance(it, LinkItem)]
            
            if sel:
                for ln in sel:
                    # Pokud je to consumption/result, převedeme na konkrétní typ podle zdroje a cíle
                    resolved_type = self._resolve_link_type(ln.src, ln.dst, lt)
                    ln.set_link_type(resolved_type)
                self.update_properties_panel()
            else:
                # Když není nic vybráno, nastaví se default pro další link
                self.default_link_type = lt
                self.cmb_default_link_type.setCurrentText(lt)

            event.accept()
            return
        
        super().keyPressEvent(event)

