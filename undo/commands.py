"""Příkazy pro undo/redo systém editoru.

Každá editační operace (přidání, smazání, přesun, změna velikosti, ...)
je implementována jako QUndoCommand, který umožňuje vrácení zpět (undo)
a opakování (redo) akce.
"""
from __future__ import annotations
from typing import List, Optional
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QUndoCommand

from graphics.nodes import ObjectItem, ProcessItem, StateItem
from graphics.link import LinkItem


class AddNodeCommand(QUndoCommand):
    """
    Příkaz pro přidání uzlu (objektu nebo procesu) do scény.
    
    Redo: Přidá uzel do scény
    Undo: Odstraní uzel ze scény
    """
    def __init__(self, scene, item, text="Add Node"):
        super().__init__(text)
        self.scene = scene
        self.item = item

    def redo(self):
        """Přidá uzel do scény (pokud tam ještě není)."""
        if not self.item.scene():
            self.scene.addItem(self.item)
        self._sync_to_global_model()

    def undo(self):
        """Odstraní uzel ze scény."""
        if self.item.scene():
            self.scene.removeItem(self.item)
        self._sync_to_global_model()
    
    def _sync_to_global_model(self):
        """Synchronizuje změnu do globálního modelu."""
        from ui.main_window import MainWindow
        main_win = MainWindow.instance()
        if main_win and hasattr(main_win, 'sync_scene_to_global_model'):
            parent_process_id = None
            for i in range(main_win.tabs.count()):
                view = main_win.tabs.widget(i)
                if view.scene() == self.scene:
                    parent_process_id = getattr(view, 'zoomed_process_id', None)
                    break
            main_win.sync_scene_to_global_model(self.scene, parent_process_id)


class AddStateCommand(QUndoCommand):
    """
    Příkaz pro přidání stavu do objektu.
    
    Stavy jsou potomky objektů (parent-child relationship v Qt Graphics).
    """
    def __init__(self, scene, parent_obj, rect, label="State"):
        super().__init__("Add State")
        self.scene = scene
        self.parent_obj = parent_obj  # Rodičovský ObjectItem
        self.rect = rect
        self.label = label
        self.item = None  # type: Optional[StateItem]

    def redo(self):
        """Přidá stav jako potomka objektu."""
        if self.item is None:
            # První volání: vytvoří nový stav jako child objektu
            # (tím se automaticky přidá do scény)
            self.item = StateItem(self.parent_obj, self.rect, self.label)
        else:
            # Po undo: znovu přiváže k rodiči
            self.item.setParentItem(self.parent_obj)
        self._sync_to_global_model()

    def undo(self):
        """Odstraní stav ze scény."""
        if self.item:
            # Nejdřív odpojí od rodiče (aby byl top-level item)
            self.item.setParentItem(None)
            # Pak teprve odstraní ze scény
            if self.item.scene():
                self.scene.removeItem(self.item)
        self._sync_to_global_model()
    
    def _sync_to_global_model(self):
        """Synchronizuje změnu do globálního modelu."""
        from ui.main_window import MainWindow
        main_win = MainWindow.instance()
        if main_win and hasattr(main_win, 'sync_scene_to_global_model'):
            parent_process_id = None
            for i in range(main_win.tabs.count()):
                view = main_win.tabs.widget(i)
                if view.scene() == self.scene:
                    parent_process_id = getattr(view, 'zoomed_process_id', None)
                    break
            main_win.sync_scene_to_global_model(self.scene, parent_process_id)



# === Mazání prvků ===

class DeleteItemsCommand(QUndoCommand):
    """
    Příkaz pro smazání vybraných prvků.
    
    Při smazání uzlu musí smazat i všechny napojené vazby.
    Při smazání objektu musí smazat i všechny jeho stavy a jejich vazby.
    """
    def __init__(self, scene: QGraphicsScene, items: List):
        super().__init__("Delete selection")
        self.scene = scene
        self.items = items[:]  # Kopie seznamu mazaných prvků
        self.links = []  # Vazby, které je potřeba smazat spolu s uzly
        
        # Sesbírá všechny vazby napojené na mazané uzly
        for it in self.items:
            if hasattr(it, "_links"):
                self.links.extend(list(it._links or []))
            # Pro stavy si uloží rodiče (pro undo)
            if isinstance(it, StateItem):
                it._saved_parent = it.parentItem()
        # Přidá vazby, které jsou přímo vybrané
        self.links.extend([it for it in self.items if isinstance(it, LinkItem)])
        # Deduplikace vazeb (podle id)
        self.links = list({id(x): x for x in self.links}.values())

    def redo(self):
        """Smaže vybrané prvky a všechny napojené vazby."""
        # Nejdřív smaže vazby
        for ln in self.links:
            if ln.scene():
                ln.remove_refs()  # Odstraní zpětné odkazy z uzlů
                self.scene.removeItem(ln)

        # Pak smaže uzly
        for it in self.items:
            if it.scene():
                # Odstraní všechny vazby uzlu
                for ln in list(getattr(it, "_links", []) or []):
                    ln.remove_refs()
                    if ln.scene():
                        self.scene.removeItem(ln)

                # Pro objekty: odstraní i vazby jejich stavů
                for ch in it.childItems():
                    if isinstance(ch, StateItem):
                        for ln in list(getattr(ch, "_links", []) or []):
                            ln.remove_refs()
                            if ln.scene():
                                self.scene.removeItem(ln)

                self.scene.removeItem(it)
        
        self._sync_to_global_model()

    def undo(self):
        """Vrátí smazané prvky zpět do scény."""
        # Nejdřív vrátí uzly
        for it in self.items:
            if not it.scene():
                # Pro stavy obnoví rodiče
                if isinstance(it, StateItem) and getattr(it, "_saved_parent", None):
                    it.setParentItem(it._saved_parent)
                self.scene.addItem(it)

        # Pak vrátí vazby a přepočítá jejich geometrii
        for ln in self.links:
            if not ln.scene():
                self.scene.addItem(ln)
                ln.update_path()  # Přepočítá cestu vazby
        
        self._sync_to_global_model()
    
    def _sync_to_global_model(self):
        """Synchronizuje změnu do globálního modelu."""
        from ui.main_window import MainWindow
        main_win = MainWindow.instance()
        if main_win and hasattr(main_win, 'sync_scene_to_global_model'):
            parent_process_id = None
            for i in range(main_win.tabs.count()):
                view = main_win.tabs.widget(i)
                if view.scene() == self.scene:
                    parent_process_id = getattr(view, 'zoomed_process_id', None)
                    break
            main_win.sync_scene_to_global_model(self.scene, parent_process_id)


class ClearAllCommand(QUndoCommand):
    """
    Příkaz pro smazání všech prvků ze scény ("Clear All").
    
    Podobné DeleteItemsCommand, ale operuje na všech prvcích.
    """
    def __init__(self, scene: QGraphicsScene):
        super().__init__("Clear all")
        self.scene = scene
        self.items = list(scene.items())  # Uloží všechny prvky pro undo
        self.links = []  # Seznam vazeb

        for it in self.items:
            # seber linky přímo z uzlu
            if hasattr(it, "_links"):
                self.links.extend(list(it._links or []))

            # seber linky od stavů (děti objektů)
            for ch in it.childItems():
                if isinstance(ch, StateItem) and hasattr(ch, "_links"):
                    self.links.extend(list(ch._links or []))
                    ch._saved_parent = ch.parentItem()

            if isinstance(it, StateItem):
                it._saved_parent = it.parentItem()

        # linky mohou být i samostatně v items
        self.links.extend([it for it in self.items if isinstance(it, LinkItem)])
        # udělej unikáty
        self.links = list({id(x): x for x in self.links}.values())

    def redo(self):
        # nejdřív linky
        for ln in self.links:
            if ln.scene():
                ln.remove_refs()
                self.scene.removeItem(ln)

        # pak všechny uzly
        for it in self.items:
            if it.scene():
                self.scene.removeItem(it)
        
        self._sync_to_global_model()

    def undo(self):
        # vrať uzly zpět (u stavů nastav rodiče)
        for it in self.items:
            if not it.scene():
                if isinstance(it, StateItem) and getattr(it, "_saved_parent", None):
                    it.setParentItem(it._saved_parent)
                self.scene.addItem(it)

        # pak linky zpět
        for ln in self.links:
            if not ln.scene():
                self.scene.addItem(ln)
                ln.update_path()
        
        self._sync_to_global_model()
    
    def _sync_to_global_model(self):
        """Synchronizuje změnu do globálního modelu."""
        from ui.main_window import MainWindow
        main_win = MainWindow.instance()
        if main_win and hasattr(main_win, 'sync_scene_to_global_model'):
            parent_process_id = None
            for i in range(main_win.tabs.count()):
                view = main_win.tabs.widget(i)
                if view.scene() == self.scene:
                    parent_process_id = getattr(view, 'zoomed_process_id', None)
                    break
            main_win.sync_scene_to_global_model(self.scene, parent_process_id)



# === Změna vlastností prvků ===

class SetLabelCommand(QUndoCommand):
    """
    Příkaz pro změnu labelu uzlu nebo vazby.
    """
    def __init__(self, item, new_label: str):
        super().__init__("Rename")
        self.item = item
        self.old = getattr(item, "label", "")  # Starý label
        self.new = new_label  # Nový label

    def redo(self):
        """Nastaví nový label."""
        if hasattr(self.item, "set_label"):
            self.item.set_label(self.new)
        # Aktualizuj globální model a hierarchický panel
        self._sync_to_global_model()

    def undo(self):
        """Obnoví starý label."""
        if hasattr(self.item, "set_label"):
            self.item.set_label(self.old)
        # Aktualizuj globální model a hierarchický panel
        self._sync_to_global_model()
    
    def _sync_to_global_model(self):
        """Synchronizuje změnu do globálního modelu."""
        from ui.main_window import MainWindow
        from graphics.nodes import ProcessItem
        
        main_win = MainWindow.instance()
        if main_win and hasattr(main_win, 'sync_scene_to_global_model'):
            scene = self.item.scene()
            if scene:
                # Najdi view pro tuto scénu
                parent_process_id = None
                for i in range(main_win.tabs.count()):
                    view = main_win.tabs.widget(i)
                    if view.scene() == scene:
                        parent_process_id = getattr(view, 'zoomed_process_id', None)
                        break
                main_win.sync_scene_to_global_model(scene, parent_process_id)
                
                # Pokud byl přejmenován proces, aktualizuj názvy tabů
                if isinstance(self.item, ProcessItem):
                    process_id = self.item.node_id
                    new_label = self.item.label
                    
                    # Aktualizuj názvy všech tabů, které zobrazují tento proces
                    for i in range(main_win.tabs.count()):
                        view = main_win.tabs.widget(i)
                        if hasattr(view, 'zoomed_process_id') and view.zoomed_process_id == process_id:
                            main_win.tabs.setTabText(i, f"🔍 {new_label}")

# ---------- Change link type ----------
class SetLinkTypeCommand(QUndoCommand):
    def __init__(self, link: LinkItem, new_type: str):
        super().__init__("Change link type")
        self.link = link
        self.old = link.link_type
        self.new = new_type

    def redo(self):
        self.link.set_link_type(self.new)

    def undo(self):
        self.link.set_link_type(self.old)

# ---------- Move item ----------
class MoveItemCommand(QUndoCommand):
    def __init__(self, item, old_pos: QPointF, new_pos: QPointF):
        super().__init__("Move")
        self.item = item
        self.old = QPointF(old_pos)
        self.new = QPointF(new_pos)

    def redo(self):
        self.item.setPos(self.new)
        for ln in getattr(self.item, "_links", []) or []:
            ln.update_path()
        self._sync_to_global_model()

    def undo(self):
        self.item.setPos(self.old)
        for ln in getattr(self.item, "_links", []) or []:
            ln.update_path()
        self._sync_to_global_model()
    
    def _sync_to_global_model(self):
        """Synchronizuje změnu do globálního modelu."""
        from ui.main_window import MainWindow
        main_win = MainWindow.instance()
        if main_win and hasattr(main_win, 'sync_scene_to_global_model'):
            scene = self.item.scene()
            if scene:
                parent_process_id = None
                for i in range(main_win.tabs.count()):
                    view = main_win.tabs.widget(i)
                    if view.scene() == scene:
                        parent_process_id = getattr(view, 'zoomed_process_id', None)
                        break
                main_win.sync_scene_to_global_model(scene, parent_process_id)

# ---------- Resize item ----------
class ResizeItemCommand(QUndoCommand):
    def __init__(self, item, old_rect: QRectF, new_rect: QRectF):
        super().__init__("Resize")
        self.item = item
        self.old = QRectF(old_rect)
        self.new = QRectF(new_rect)

    def redo(self):
        self.item.setRect(self.new)
        for ln in getattr(self.item, "_links", []) or []:
            ln.update_path()
        self._sync_to_global_model()

    def undo(self):
        self.item.setRect(self.old)
        for ln in getattr(self.item, "_links", []) or []:
            ln.update_path()
        self._sync_to_global_model()
    
    def _sync_to_global_model(self):
        """Synchronizuje změnu do globálního modelu."""
        from ui.main_window import MainWindow
        main_win = MainWindow.instance()
        if main_win and hasattr(main_win, 'sync_scene_to_global_model'):
            scene = self.item.scene()
            if scene:
                parent_process_id = None
                for i in range(main_win.tabs.count()):
                    view = main_win.tabs.widget(i)
                    if view.scene() == scene:
                        parent_process_id = getattr(view, 'zoomed_process_id', None)
                        break
                main_win.sync_scene_to_global_model(scene, parent_process_id)