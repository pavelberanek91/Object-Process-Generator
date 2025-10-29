"""Systém pro změnu velikosti uzlů pomocí resize handles (táhel).

Implementuje:
- ResizeHandle: Malé čtverce na okrajích uzlu pro změnu velikosti
- ResizableMixin: Mixin přidávající 8 resize handles uzlům
- Snap na mřížku při změně velikosti
- Minimální rozměry uzlů
"""
from typing import Optional
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QCursor, QPen, QBrush
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from constants import HANDLE_SIZE, GRID_SIZE, MIN_NODE_W, MIN_NODE_H


def _snapf(x: float) -> float:
    """Zarovná souřadnici na nejbližší násobek GRID_SIZE."""
    return round(x / GRID_SIZE) * GRID_SIZE


class ResizeHandle(QGraphicsRectItem):
    """
    Malé táhlo pro změnu velikosti rodičovského uzlu.

    Táhlo je potomkem uzlu (Object/Process), ignoruje transformace (stálá velikost na obrazovce)
    a při táhnutí volá metody `begin_resize`, `request_resize` a `end_resize` na parentu.
    """

    def __init__(self, parent: QGraphicsItem, role: str):
        # role ∈ {"n","s","e","w","ne","nw","se","sw"}
        super().__init__(-HANDLE_SIZE/2, -HANDLE_SIZE/2, HANDLE_SIZE, HANDLE_SIZE, parent)
        self.setZValue(1000)  # nad tvarem
        self.setBrush(QBrush(Qt.white))
        self.setPen(QPen(Qt.black, 1))
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.role = role
        self._pressed = False

        # Kurzory podle směru
        cursors = {
            "n": Qt.SizeVerCursor, "s": Qt.SizeVerCursor,
            "e": Qt.SizeHorCursor, "w": Qt.SizeHorCursor,
            "ne": Qt.SizeBDiagCursor, "sw": Qt.SizeBDiagCursor,
            "nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor,
        }
        self.setCursor(QCursor(cursors.get(role, Qt.SizeAllCursor)))

    def mousePressEvent(self, event):
        event.accept()
        par = self.parentItem()
        if hasattr(par, "begin_resize"):
            par.begin_resize(self.role, event.scenePos())   # dříve: mapToScene(event.position())
        # super().mousePressEvent(event)  # volitelné – většinou už není potřeba

    def mouseMoveEvent(self, event):
        # if not self._pressed:
        #     event.ignore()
        #     return
        # # přepošleme na parent (ten ví, jak změnit svůj rect)
        # par = self.parentItem()
        # if par and hasattr(par, "request_resize"):
        #     par.request_resize(self.role, event.scenePos())
        #     #par.request_resize(self.role, self.mapToScene(event.pos()))
        # event.accept()
        event.accept()
        par = self.parentItem()
        if hasattr(par, "request_resize"):
            par.request_resize(self.role, event.scenePos()) # dříve: mapToScene(event.position())
        # super().mouseMoveEvent(event)  # volitelné

    def mouseReleaseEvent(self, event):
        # self._pressed = False
        # event.accept()
        event.accept()
        par = self.parentItem()
        if hasattr(par, "end_resize"):
            par.end_resize(self.role, event.scenePos())     # dříve: mapToScene(event.position())
        # super().mouseReleaseEvent(event)  # volitelné


class ResizableMixin:
    """Mixin pro uzly (Rect/Ellipse) – přidává 8 táhel a logiku přepočtu nového rectu."""

    _handles: dict[str, ResizeHandle]
    _min_w: float = MIN_NODE_W
    _min_h: float = MIN_NODE_H

    def _init_resize(self):
        # Vytvoření táhel; viditelnost budeme přepínat podle výběru uzlu
        self._handles = {}
        for role in ("n","s","e","w","ne","nw","se","sw"):
            h = ResizeHandle(self, role)
            h.setVisible(False)
            self._handles[role] = h
        self._layout_handles()

    def _layout_handles(self):
        """Rozmístí táhla kolem current rect() v lokálních souřadnicích uzlu."""
        if not hasattr(self, "rect"):
            return
        r: QRectF = self.rect()
        cx, cy = r.center().x(), r.center().y()
        pos = {
            "n":  QPointF(cx, r.top()),
            "s":  QPointF(cx, r.bottom()),
            "w":  QPointF(r.left(), cy),
            "e":  QPointF(r.right(), cy),
            "nw": QPointF(r.left(), r.top()),
            "ne": QPointF(r.right(), r.top()),
            "sw": QPointF(r.left(), r.bottom()),
            "se": QPointF(r.right(), r.bottom()),
        }
        for role, h in self._handles.items():
            h.setPos(pos[role])

    def request_resize(self, role: str, scene_pos: QPointF):
        """Požadavek od handle: přepočti a nastav nový rect."""
        if not hasattr(self, "rect"):
            return
        # Převod na lokální souřadnice uzlu
        p = self.mapFromScene(scene_pos)
        r0: QRectF = self.rect()

        # Zvolíme ukotvený (protější) roh/hranici podle role
        # a přepočítáme nový QRectF. Poté aplikujeme minimální rozměry a snap.
        left, right, top, bottom = r0.left(), r0.right(), r0.top(), r0.bottom()

        if role in ("e","ne","se"):
            right = p.x()
        if role in ("w","nw","sw"):
            left = p.x()
        if role in ("s","se","sw"):
            bottom = p.y()
        if role in ("n","ne","nw"):
            top = p.y()

        # normování, aby left <= right, top <= bottom
        if left > right: left, right = right, left
        if top > bottom: top, bottom = bottom, top

        # snap + minimální rozměry
        left, right = _snapf(left), _snapf(right)
        top, bottom = _snapf(top), _snapf(bottom)

        w = max(right - left, self._min_w)
        h = max(bottom - top, self._min_h)

        # udrž pozici „ukotveného“ rohu: pokud jsme kvůli min velikosti museli rozšířit,
        # opravíme stranu podle role
        if role in ("e","ne","se"):
            right = left + w
        elif role in ("w","nw","sw"):
            left = right - w

        if role in ("s","se","sw"):
            bottom = top + h
        elif role in ("n","ne","nw"):
            top = bottom - h

        new_rect = QRectF(left, top, right - left, bottom - top)

        # Aplikace a přepočet geometrie/linků/handle pozic
        self.prepareGeometryChange()
        # setRect existuje na QGraphicsRectItem i QGraphicsEllipseItem
        self.setRect(new_rect)
        self._layout_handles()
        # Uzly mají v našem projektu seznam odkazů v self._links → překreslíme cesty
        for ln in getattr(self, "_links", []) or []:
            ln.update_path()

    def _set_handles_visible(self, vis: bool):
        for h in self._handles.values():
            h.setVisible(vis)