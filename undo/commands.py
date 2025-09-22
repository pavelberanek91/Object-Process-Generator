# undo/commands.py
from __future__ import annotations
from typing import List, Optional
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QUndoCommand

# Typy z tvého projektu
from graphics.nodes import ObjectItem, ProcessItem, StateItem
from graphics.link import LinkItem

class AddNodeCommand(QUndoCommand):
    """
    Univerzální příkaz pro přidání ObjectItem nebo ProcessItem do scény.
    """
    def __init__(self, scene, item, text="Add Node"):
        super().__init__(text)
        self.scene = scene
        self.item = item

    def redo(self):
        if not self.item.scene():
            self.scene.addItem(self.item)
        self.item.setSelected(True)

    def undo(self):
        if self.item.scene():
            self.scene.removeItem(self.item)


class AddStateCommand(QUndoCommand):
    def __init__(self, scene, parent_obj, rect, label="State"):
        super().__init__("Add State")
        self.scene = scene
        self.parent_obj = parent_obj
        self.rect = rect
        self.label = label
        self.item = None  # type: Optional[StateItem]

    def redo(self):
        if self.item is None:
            # vytvoř jako child – TÍM JE AUTOMATICKY VE SCÉNĚ rodiče
            self.item = StateItem(self.parent_obj, self.rect, self.label)
        else:
            # po undo – stačí znovu přivázat k rodiči (do scény už se nevolá addItem)
            self.item.setParentItem(self.parent_obj)
        self.item.setSelected(True)

    def undo(self):
        if self.item:
            # nejdřív odpoj od rodiče (aby nebyl child)
            self.item.setParentItem(None)
            # a pak teprve odstranění ze scény (teď je top-level)
            if self.item.scene():
                self.scene.removeItem(self.item)



# ---------- Delete selection ----------
class DeleteItemsCommand(QUndoCommand):
    def __init__(self, scene: QGraphicsScene, items: List):
        super().__init__("Delete selection")
        self.scene = scene
        self.items = items[:]
        self.links = []
        for it in self.items:
            if hasattr(it, "_links"):
                self.links.extend(list(it._links or []))
            if isinstance(it, StateItem):
                it._saved_parent = it.parentItem()
        self.links.extend([it for it in self.items if isinstance(it, LinkItem)])
        self.links = list({id(x): x for x in self.links}.values())

    def redo(self):
        for ln in self.links:
            if ln.scene():
                ln.remove_refs()
                self.scene.removeItem(ln)
        for it in self.items:
            if it.scene():
                for ln in list(getattr(it, "_links", []) or []):
                    ln.remove_refs()
                    if ln.scene():
                        self.scene.removeItem(ln)
                # DŮLEŽITÉ: odpojit state od parenta před removeItem
                if isinstance(it, StateItem):
                    it.setParentItem(None)
                self.scene.removeItem(it)

    def undo(self):
        # nejdřív vrátit uzly (StateItem bez addItem, jen parent); pak linky
        for it in self.items:
            if not it.scene():
                if isinstance(it, StateItem):
                    parent = getattr(it, "_saved_parent", None)
                    if parent:
                        it.setParentItem(parent)   # do scény se dostane přes parenta
                else:
                    self.scene.addItem(it)        # top-level uzly se přidávají do scény
        for ln in self.links:
            if not ln.scene():
                self.scene.addItem(ln)
                ln.update_path()


class ClearAllCommand(QUndoCommand):
    def __init__(self, scene: QGraphicsScene):
        super().__init__("Clear all")
        self.scene = scene
        self.items = list(scene.items())
        self.links = []
        for it in self.items:
            if hasattr(it, "_links"):
                self.links.extend(list(it._links or []))
            if isinstance(it, StateItem):
                it._saved_parent = it.parentItem()
        self.links.extend([it for it in self.items if isinstance(it, LinkItem)])
        self.links = list({id(x): x for x in self.links}.values())

    def redo(self):
        for ln in self.links:
            if ln.scene():
                ln.remove_refs()
                self.scene.removeItem(ln)
        for it in self.items:
            if it.scene():
                if isinstance(it, StateItem):
                    it.setParentItem(None)  # odpoj child
                self.scene.removeItem(it)

    def undo(self):
        for it in self.items:
            if not it.scene():
                if isinstance(it, StateItem):
                    parent = getattr(it, "_saved_parent", None)
                    if parent:
                        it.setParentItem(parent)  # bez addItem
                else:
                    self.scene.addItem(it)        # top-level zpět do scény
        for ln in self.links:
            if not ln.scene():
                self.scene.addItem(ln)
                ln.update_path()


# ---------- Set label ----------
class SetLabelCommand(QUndoCommand):
    def __init__(self, item, new_label: str):
        super().__init__("Rename")
        self.item = item
        self.old = getattr(item, "label", "")
        self.new = new_label

    def redo(self):
        if hasattr(self.item, "set_label"):
            self.item.set_label(self.new)

    def undo(self):
        if hasattr(self.item, "set_label"):
            self.item.set_label(self.old)

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

    def undo(self):
        self.item.setPos(self.old)
        for ln in getattr(self.item, "_links", []) or []:
            ln.update_path()

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

    def undo(self):
        self.item.setRect(self.old)
        for ln in getattr(self.item, "_links", []) or []:
            ln.update_path()