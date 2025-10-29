"""
Hierarchický panel pro zobrazení a navigaci procesů.
"""

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QDockWidget, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
    QVBoxLayout, QWidget
)


class ProcessHierarchyPanel(QDockWidget):
    """Panel pro zobrazení hierarchie procesů."""
    
    navigateToProcess = Signal(str, str)  # process_id, parent_process_id
    
    def __init__(self, parent=None):
        super().__init__("Hierarchie procesů", parent)
        self.main_window = parent
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._init_ui()
        self.item_to_process = {}  # Map item ID -> process data
        self._is_refreshing = False  # Ochrana proti rekurzivním voláním
        
        # Debouncing pro kliknutí - zabraňuje příliš rychlému přepínání
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(100)  # 100ms delay
        self._pending_click_data = None
    
    def _init_ui(self):
        """Inicializuje UI panelu."""
        container = QWidget(self)
        layout = QVBoxLayout(container)
        
        # Strom procesů
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Procesy")
        self.tree.setAlternatingRowColors(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)
        
        self.setWidget(container)
    
    def refresh_tree(self):
        """Obnoví strom procesů z dat."""
        # Ochrana proti rekurzivním voláním
        if self._is_refreshing:
            return
        
        self._is_refreshing = True
        try:
            # Uložíme rozbalený stav
            expanded_ids = self._get_expanded_process_ids()
            selected_id = self._get_selected_process_id()
            
            self.tree.clear()
            self.item_to_process = {}
            
            if not self.main_window or not hasattr(self.main_window, '_global_diagram_data'):
                return
            
            # Získej všechny procesy
            nodes = self.main_window._global_diagram_data.get("nodes", [])
            processes = [n for n in nodes if n.get("kind") == "process"]
            
            # Najdi root procesy (bez parent_process_id)
            root_processes = [p for p in processes if not p.get("parent_process_id")]
            
            # Vytvoř kořenovou položku pro root canvas
            root_item = QTreeWidgetItem(self.tree)
            root_item.setText(0, "🏠 Root Canvas")
            root_item.setData(0, Qt.UserRole, None)  # None značí root
            
            # Ulož mapping pro root
            self.item_to_process[id(root_item)] = {
                "process_id": None,
                "parent_process_id": None
            }
            
            # Vytvoř slovník procesů podle ID
            process_dict = {p["id"]: p for p in processes}
            
            # Přidej root procesy pod root item
            for process in root_processes:
                self._add_process_to_tree(process, root_item, process_dict, processes)
            
            # Automaticky rozbal root item
            root_item.setExpanded(True)
            
            # Obnov rozbalený stav
            self._restore_expanded_state(expanded_ids)
            self._restore_selection(selected_id)
        except Exception as e:
            print(f"Error in refresh_tree: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_refreshing = False
    
    def _add_process_to_tree(self, process, parent_item, process_dict, all_processes):
        """Rekurzivně přidá proces a jeho podprocesy do stromu."""
        process_id = process["id"]
        process_label = process.get("label", "Process")
        parent_process_id = process.get("parent_process_id")
        
        # Najdi podprocesy
        children = [p for p in all_processes if p.get("parent_process_id") == process_id]
        child_count = len(children)
        
        # Vytvoř text s ikonou
        if child_count > 0:
            text = f"📁 {process_label} ({child_count})"
        else:
            text = f"📄 {process_label}"
        
        # Vytvoř item
        if parent_item is None:
            item = QTreeWidgetItem(self.tree)
        else:
            item = QTreeWidgetItem(parent_item)
        
        item.setText(0, text)
        item.setData(0, Qt.UserRole, process_id)
        
        # Ulož mapping
        self.item_to_process[id(item)] = {
            "process_id": process_id,
            "parent_process_id": parent_process_id
        }
        
        # Rekurzivně přidej podprocesy (zachovej pořadí z all_processes)
        for child in children:
            self._add_process_to_tree(child, item, process_dict, all_processes)
    
    def _on_item_clicked(self, item, column):
        """Handler pro kliknutí na item - s debouncing."""
        try:
            process_data = self.item_to_process.get(id(item))
            if not process_data:
                return
            
            # Zastaví předchozí čekající click
            if self._click_timer.isActive():
                self._click_timer.stop()
            
            # Uloží data pro zpožděné provedení
            self._pending_click_data = process_data.copy()
            
            # Nastaví timer pro provedení za 100ms
            self._click_timer.timeout.connect(self._process_delayed_click)
            self._click_timer.start()
            
        except Exception as e:
            print(f"Error in _on_item_clicked: {e}")
            import traceback
            traceback.print_exc()
    
    def _process_delayed_click(self):
        """Zpracuje click se zpožděním (debouncing)."""
        try:
            # Odpojí signál
            self._click_timer.timeout.disconnect(self._process_delayed_click)
            
            if not self._pending_click_data:
                return
            
            process_id = self._pending_click_data["process_id"]
            parent_process_id = self._pending_click_data["parent_process_id"]
            
            print(f"[Hierarchy] Navigating to process_id={process_id}, parent={parent_process_id}")
            
            # Pokud je process_id None, jde o root canvas
            if process_id is None:
                # Naviguj na root canvas
                if self.main_window:
                    self.main_window.navigate_to_root_canvas()
            else:
                # Naviguj do in-zoom view procesu
                if self.main_window:
                    self.main_window.navigate_into_process_by_id(process_id, parent_process_id)
            
            self._pending_click_data = None
            
        except Exception as e:
            print(f"Error in _process_delayed_click: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_expanded_process_ids(self):
        """Vrátí množinu ID rozbalených procesů."""
        expanded = set()
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                process_id = item.data(0, Qt.UserRole)
                if process_id:
                    expanded.add(process_id)
            iterator += 1
        return expanded
    
    def _get_selected_process_id(self):
        """Vrátí ID vybraného procesu."""
        selected_items = self.tree.selectedItems()
        if selected_items:
            return selected_items[0].data(0, Qt.UserRole)
        return None
    
    def _restore_expanded_state(self, expanded_ids):
        """Obnoví rozbalený stav procesů."""
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            process_id = item.data(0, Qt.UserRole)
            if process_id in expanded_ids:
                item.setExpanded(True)
            iterator += 1
    
    def _restore_selection(self, process_id):
        """Obnoví výběr procesu."""
        if not process_id:
            return
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) == process_id:
                self.tree.setCurrentItem(item)
                break
            iterator += 1

